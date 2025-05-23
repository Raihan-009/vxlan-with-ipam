from fastapi import FastAPI, HTTPException
import requests
import docker
import socket
import subprocess
from config import IPAM_SERVICE_URL, CONTAINER_SERVICE_PORT

app = FastAPI(title="VXLAN Container Service")

# Docker client
client = docker.from_env()

def get_host_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip

HOST_ID = get_host_ip()

def assign_container_ip(container_name, ip_address):
    """Assign IP address to container in VXLAN network"""
    try:
        # Get container
        container = client.containers.get(container_name)
        
        # Connect container to VXLAN network with specific IP
        network = client.networks.get("vxlan-net")
        network.connect(container, ipv4_address=ip_address)
        
        return True
    except Exception as e:
        print(f"Failed to assign IP {ip_address} to {container_name}: {e}")
        return False

@app.get("/health")
async def health_check():
    """Health check and VXLAN network verification"""
    try:
        # Test IPAM connectivity
        response = requests.get(f"{IPAM_SERVICE_URL}/", timeout=5)
        ipam_status = "healthy" if response.status_code == 200 else "unhealthy"
    except Exception as e:
        ipam_status = f"unreachable: {str(e)}"
    
    # Check Docker
    try:
        client.ping()
        docker_status = "healthy"
    except Exception as e:
        docker_status = f"unhealthy: {str(e)}"
    
    # Check VXLAN network
    try:
        network = client.networks.get("vxlan-net")
        vxlan_status = "healthy"
        vxlan_subnet = network.attrs['IPAM']['Config'][0]['Subnet']
    except Exception as e:
        vxlan_status = f"missing: {str(e)}"
        vxlan_subnet = "unknown"
    
    # Check VXLAN interface
    try:
        result = subprocess.run(['ip', 'link', 'show', 'vxlan0'], 
                              capture_output=True, text=True)
        vxlan_interface = "up" if "UP" in result.stdout else "down"
    except:
        vxlan_interface = "missing"
    
    return {
        "status": "healthy",
        "host_id": HOST_ID,
        "ipam_connection": ipam_status,
        "docker_status": docker_status,
        "vxlan_network": vxlan_status,
        "vxlan_subnet": vxlan_subnet,
        "vxlan_interface": vxlan_interface,
        "ipam_url": IPAM_SERVICE_URL
    }

@app.post("/create_container")
async def create_container(container_name: str, image: str = "nginx:alpine"):
    """Create a container with IP from IPAM and connect to VXLAN"""
    
    # 1. Check if container name already exists globally
    try:
        check_response = requests.get(f"{IPAM_SERVICE_URL}/check/{container_name}")
        if check_response.status_code == 200:
            check_data = check_response.json()
            if check_data.get("exists"):
                raise HTTPException(
                    status_code=400, 
                    detail=f"Container name '{container_name}' already exists on host {check_data.get('host_id')}"
                )
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Failed to check container name: {e}")
    
    # 2. Request IP from IPAM service
    try:
        response = requests.post(f"{IPAM_SERVICE_URL}/allocate", json={
            "container_name": container_name,
            "host_id": HOST_ID
        })
        response.raise_for_status()
        ip_data = response.json()
        allocated_ip = ip_data["ip_address"]
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"IPAM allocation failed: {e}")
    
    # 3. Create container (without network initially)
    try:
        container = client.containers.run(
            image,
            name=container_name,
            detach=True,
            labels={
                "vxlan.ip": allocated_ip, 
                "vxlan.host": HOST_ID,
                "vxlan.managed": "true"
            }
        )
        
        # 4. Connect container to VXLAN network with allocated IP
        try:
            network = client.networks.get("vxlan-net")
            network.connect(container, ipv4_address=allocated_ip)
            network_status = "connected"
        except Exception as e:
            network_status = f"failed: {str(e)}"
        
        return {
            "container_id": container.id[:12],
            "container_name": container_name,
            "ip_address": allocated_ip,
            "host": HOST_ID,
            "image": image,
            "status": "created",
            "network_status": network_status
        }
        
    except Exception as e:
        # If container creation fails, release the IP
        try:
            requests.post(f"{IPAM_SERVICE_URL}/release", json={
                "container_name": container_name
            })
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Container creation failed: {e}")

@app.delete("/container/{container_name}")
async def delete_container(container_name: str):
    """Delete container and release its IP"""
    
    try:
        container = client.containers.get(container_name)
        allocated_ip = container.labels.get("vxlan.ip", "unknown")
        
        # Disconnect from VXLAN network first
        try:
            network = client.networks.get("vxlan-net")
            network.disconnect(container, force=True)
        except:
            pass  # Ignore disconnect errors
        
        # Remove container
        container.remove(force=True)
        
        # Release IP back to IPAM
        try:
            response = requests.post(f"{IPAM_SERVICE_URL}/release", json={
                "container_name": container_name
            })
            release_status = "released" if response.status_code == 200 else "failed"
        except Exception as e:
            release_status = f"failed: {e}"
        
        return {
            "message": f"Container {container_name} deleted",
            "ip_address": allocated_ip,
            "ip_release_status": release_status
        }
        
    except docker.errors.NotFound:
        raise HTTPException(status_code=404, detail="Container not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/containers")
async def list_local_containers():
    """List containers running on this host"""
    containers = []
    
    for container in client.containers.list(all=True):
        if container.labels.get("vxlan.managed") == "true":
            # Get network info
            networks = container.attrs.get('NetworkSettings', {}).get('Networks', {})
            vxlan_ip = networks.get('vxlan-net', {}).get('IPAddress', 'not connected')
            
            containers.append({
                "name": container.name,
                "id": container.id[:12],
                "status": container.status,
                "allocated_ip": container.labels.get("vxlan.ip"),
                "actual_ip": vxlan_ip,
                "image": container.image.tags[0] if container.image.tags else "unknown"
            })
    
    return {
        "host_id": HOST_ID,
        "containers": containers,
        "count": len(containers)
    }

@app.post("/test_connectivity")
async def test_connectivity(container_name: str, target_ip: str):
    """Test network connectivity from container to target IP"""
    try:
        container = client.containers.get(container_name)
        
        # Execute ping command inside container
        result = container.exec_run(f"ping -c 3 {target_ip}", demux=True)
        
        return {
            "container": container_name,
            "target": target_ip,
            "exit_code": result.exit_code,
            "output": result.output[0].decode() if result.output[0] else "",
            "error": result.output[1].decode() if result.output[1] else "",
            "success": result.exit_code == 0
        }
    except docker.errors.NotFound:
        raise HTTPException(status_code=404, detail="Container not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=CONTAINER_SERVICE_PORT)