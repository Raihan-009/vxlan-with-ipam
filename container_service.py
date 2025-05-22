# /opt/vxlan-cluster/container_service.py
# container_service.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import docker
import requests
import socket
from typing import List, Optional
from config import *

app = FastAPI(
    title="VXLAN Container Service",
    description="Container Management for VXLAN Cluster",
    version="1.0.0"
)

# Docker client
docker_client = docker.from_env()

# Get current host ID
def get_host_id():
    """Get the current host identifier"""
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    if local_ip == HOST1_IP:
        return "host1"
    elif local_ip == HOST2_IP:
        return "host2"
    else:
        return f"host-{local_ip}"

HOST_ID = get_host_id()
IPAM_URL = f"http://{HOST1_IP}:{IPAM_PORT}"

# Request/Response Models
class ContainerCreateRequest(BaseModel):
    name: str
    image: str = "nginx:alpine"
    ports: Optional[dict] = None

class ContainerResponse(BaseModel):
    container_id: str
    name: str
    image: str
    ip_address: str
    host_id: str
    status: str
    ports: Optional[dict] = None

class ContainerListResponse(BaseModel):
    containers: List[ContainerResponse]
    host_id: str
    total_count: int

# Helper Functions
def check_container_exists_globally(container_name: str):
    """Check if container name exists globally in IPAM"""
    try:
        response = requests.get(
            f"{IPAM_URL}/check/{container_name}",
            timeout=5
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        # If IPAM is unreachable, assume container doesn't exist
        print(f"Warning: Could not check IPAM for container {container_name}: {str(e)}")
        return {"exists": False}

def request_ip_from_ipam(container_name: str):
    """Request IP allocation from IPAM service"""
    try:
        response = requests.post(
            f"{IPAM_URL}/allocate",
            json={"container_name": container_name, "host_id": HOST_ID},
            timeout=10
        )
        response.raise_for_status()
        return response.json()["ip_address"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to allocate IP: {str(e)}")

def release_ip_to_ipam(container_name: str):
    """Release IP back to IPAM service"""
    try:
        response = requests.post(
            f"{IPAM_URL}/release",
            json={"container_name": container_name},
            timeout=10
        )
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Failed to release IP for {container_name}: {str(e)}")
        return False

def get_container_info(container):
    """Extract container information"""
    try:
        # Get container IP
        networks = container.attrs['NetworkSettings']['Networks']
        ip_address = networks.get(DOCKER_NETWORK_NAME, {}).get('IPAddress', 'unknown')
        
        # Get port mappings
        ports = container.attrs['NetworkSettings']['Ports']
        
        return ContainerResponse(
            container_id=container.id[:12],
            name=container.name,
            image=container.image.tags[0] if container.image.tags else container.image.id[:12],
            ip_address=ip_address,
            host_id=HOST_ID,
            status=container.status,
            ports=ports
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get container info: {str(e)}")

# API Endpoints
@app.get("/", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    try:
        # Test Docker connection
        docker_client.ping()
        docker_status = "connected"
    except:
        docker_status = "disconnected"
    
    try:
        # Test IPAM connection
        response = requests.get(f"{IPAM_URL}/", timeout=5)
        ipam_status = "connected" if response.status_code == 200 else "error"
    except:
        ipam_status = "disconnected"
    
    return {
        "status": "healthy",
        "service": "Container Service",
        "host_id": HOST_ID,
        "docker": docker_status,
        "ipam": ipam_status
    }

@app.post("/containers", response_model=ContainerResponse, tags=["Container Management"])
async def create_container(request: ContainerCreateRequest):
    """Create a new container with automatic IP allocation"""
    
    # Check if container name already exists globally
    global_check = check_container_exists_globally(request.name)
    if global_check["exists"]:
        existing_host = global_check.get("host_id", "unknown")
        existing_ip = global_check.get("ip_address", "unknown")
        raise HTTPException(
            status_code=409, 
            detail=f"Container '{request.name}' already exists on {existing_host} with IP {existing_ip}"
        )
    
    # Check if container name already exists locally
    try:
        existing = docker_client.containers.get(request.name)
        if existing:
            raise HTTPException(
                status_code=409, 
                detail=f"Container '{request.name}' already exists locally on {HOST_ID}"
            )
    except docker.errors.NotFound:
        pass  # Container doesn't exist locally, which is what we want
    
    # Request IP from IPAM
    ip_address = request_ip_from_ipam(request.name)
    
    try:
        # Prepare container configuration
        container_config = {
            "image": request.image,
            "name": request.name,
            "network": DOCKER_NETWORK_NAME,
            "detach": True,
            "hostname": request.name
        }
        
        # Add port mappings if specified
        if request.ports:
            container_config["ports"] = request.ports
        
        # Create and start container
        container = docker_client.containers.run(**container_config)
        
        # Set the allocated IP
        network = docker_client.networks.get(DOCKER_NETWORK_NAME)
        network.disconnect(container)
        network.connect(container, ipv4_address=ip_address)
        
        # Reload container to get updated info
        container.reload()
        
        return get_container_info(container)
        
    except Exception as e:
        # If container creation fails, release the IP
        release_ip_to_ipam(request.name)
        raise HTTPException(status_code=500, detail=f"Failed to create container: {str(e)}")

@app.get("/containers", response_model=ContainerListResponse, tags=["Container Management"])
async def list_containers():
    """List all containers on this host"""
    
    try:
        containers = docker_client.containers.list(all=True)
        container_list = []
        
        for container in containers:
            # Only include containers on our VXLAN network
            networks = container.attrs['NetworkSettings']['Networks']
            if DOCKER_NETWORK_NAME in networks:
                container_list.append(get_container_info(container))
        
        return ContainerListResponse(
            containers=container_list,
            host_id=HOST_ID,
            total_count=len(container_list)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list containers: {str(e)}")

@app.get("/containers/{container_name}", response_model=ContainerResponse, tags=["Container Management"])
async def get_container(container_name: str):
    """Get information about a specific container"""
    
    try:
        container = docker_client.containers.get(container_name)
        return get_container_info(container)
    except docker.errors.NotFound:
        raise HTTPException(status_code=404, detail=f"Container {container_name} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get container: {str(e)}")

@app.delete("/containers/{container_name}", tags=["Container Management"])
async def delete_container(container_name: str):
    """Delete a container and release its IP"""
    
    try:
        container = docker_client.containers.get(container_name)
        
        # Stop and remove container
        container.stop(timeout=10)
        container.remove()
        
        # Release IP back to IPAM
        release_ip_to_ipam(container_name)
        
        return {"message": f"Container {container_name} deleted successfully"}
        
    except docker.errors.NotFound:
        # Container doesn't exist, but try to release IP anyway
        release_ip_to_ipam(container_name)
        raise HTTPException(status_code=404, detail=f"Container {container_name} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete container: {str(e)}")

@app.post("/containers/{container_name}/start", tags=["Container Management"])
async def start_container(container_name: str):
    """Start a stopped container"""
    
    try:
        container = docker_client.containers.get(container_name)
        container.start()
        container.reload()
        return get_container_info(container)
    except docker.errors.NotFound:
        raise HTTPException(status_code=404, detail=f"Container {container_name} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start container: {str(e)}")

@app.post("/containers/{container_name}/stop", tags=["Container Management"])
async def stop_container(container_name: str):
    """Stop a running container"""
    
    try:
        container = docker_client.containers.get(container_name)
        container.stop(timeout=10)
        container.reload()
        return get_container_info(container)
    except docker.errors.NotFound:
        raise HTTPException(status_code=404, detail=f"Container {container_name} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop container: {str(e)}")

@app.get("/network/info", tags=["Network"])
async def get_network_info():
    """Get VXLAN network information"""
    
    try:
        network = docker_client.networks.get(DOCKER_NETWORK_NAME)
        return {
            "network_name": DOCKER_NETWORK_NAME,
            "network_id": network.id[:12],
            "driver": network.attrs['Driver'],
            "subnet": network.attrs['IPAM']['Config'][0]['Subnet'],
            "gateway": network.attrs['IPAM']['Config'][0]['Gateway'],
            "containers": len(network.attrs['Containers'])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get network info: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=CONTAINER_SERVICE_PORT)
