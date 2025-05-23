from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import redis
import ipaddress
import json
from typing import List, Optional
from config import *

app = FastAPI(
    title="VXLAN IPAM Service",
    description="IP Address Management for VXLAN Container Cluster",
    version="1.0.0"
)

# Redis connection
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)

# Request/Response Models
class IPAllocationRequest(BaseModel):
    container_name: str
    host_id: str

class IPAllocationResponse(BaseModel):
    ip_address: str
    container_name: str
    host_id: str
    success: bool

class IPReleaseRequest(BaseModel):
    container_name: str

class ContainerInfo(BaseModel):
    container_name: str
    ip_address: str
    host_id: str

class IPAMStats(BaseModel):
    total_ips: int
    allocated_ips: int
    available_ips: int
    network_subnet: str

# Initialize IP pool
def init_ip_pool():
    """Initialize the IP address pool in Redis"""
    if r.exists("ipam_initialized"):
        return
    
    # Clear any existing data
    r.flushdb()
    
    # Generate available IP addresses
    network = ipaddress.IPv4Network(NETWORK_SUBNET)
    start_ip = ipaddress.IPv4Address(NETWORK_START)
    end_ip = ipaddress.IPv4Address(NETWORK_END)
    
    available_count = 0
    for ip in network.hosts():
        if start_ip <= ip <= end_ip:
            r.sadd("available_ips", str(ip))
            available_count += 1
    
    r.set("ipam_initialized", "true")
    print(f"Initialized IPAM with {available_count} available IP addresses")

# API Endpoints
@app.on_event("startup")
async def startup_event():
    init_ip_pool()

@app.get("/", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "IPAM", "host": IPAM_NODE_IP}

@app.post("/allocate", response_model=IPAllocationResponse, tags=["IP Management"])
async def allocate_ip(request: IPAllocationRequest):
    """Allocate an IP address for a container"""
    
    # Check if container already has an IP
    existing_ip = r.hget("container_ips", request.container_name)
    if existing_ip:
        return IPAllocationResponse(
            ip_address=existing_ip,
            container_name=request.container_name,
            host_id=request.host_id,
            success=True
        )
    
    # Get an available IP
    available_ip = r.spop("available_ips")
    if not available_ip:
        raise HTTPException(status_code=400, detail="No available IP addresses")
    
    # Allocate the IP
    r.hset("container_ips", request.container_name, available_ip)
    r.hset("ip_containers", available_ip, request.container_name)
    r.hset("container_hosts", request.container_name, request.host_id)
    r.sadd("allocated_ips", available_ip)
    
    return IPAllocationResponse(
        ip_address=available_ip,
        container_name=request.container_name,
        host_id=request.host_id,
        success=True
    )

@app.post("/release", tags=["IP Management"])
async def release_ip(request: IPReleaseRequest):
    """Release an IP address from a container"""
    
    # Get the IP for this container
    ip_address = r.hget("container_ips", request.container_name)
    if not ip_address:
        raise HTTPException(status_code=404, detail="Container not found")
    
    # Release the IP
    r.hdel("container_ips", request.container_name)
    r.hdel("ip_containers", ip_address)
    r.hdel("container_hosts", request.container_name)
    r.srem("allocated_ips", ip_address)
    r.sadd("available_ips", ip_address)
    
    return {"message": f"IP {ip_address} released from {request.container_name}"}

@app.get("/stats", response_model=IPAMStats, tags=["Monitoring"])
async def get_stats():
    """Get IPAM statistics"""
    
    network = ipaddress.IPv4Network(NETWORK_SUBNET)
    start_ip = ipaddress.IPv4Address(NETWORK_START)
    end_ip = ipaddress.IPv4Address(NETWORK_END)
    
    total_ips = len([ip for ip in network.hosts() if start_ip <= ip <= end_ip])
    allocated_ips = r.scard("allocated_ips")
    available_ips = r.scard("available_ips")
    
    return IPAMStats(
        total_ips=total_ips,
        allocated_ips=allocated_ips,
        available_ips=available_ips,
        network_subnet=NETWORK_SUBNET
    )

@app.get("/containers", response_model=List[ContainerInfo], tags=["Monitoring"])
async def list_containers():
    """List all allocated containers"""
    
    containers = []
    container_ips = r.hgetall("container_ips")
    container_hosts = r.hgetall("container_hosts")
    
    for container_name, ip_address in container_ips.items():
        host_id = container_hosts.get(container_name, "unknown")
        containers.append(ContainerInfo(
            container_name=container_name,
            ip_address=ip_address,
            host_id=host_id
        ))
    
    return containers

@app.get("/container/{container_name}", tags=["Monitoring"])
async def get_container_info(container_name: str):
    """Get information about a specific container"""
    
    ip_address = r.hget("container_ips", container_name)
    if not ip_address:
        raise HTTPException(status_code=404, detail="Container not found")
    
    host_id = r.hget("container_hosts", container_name)
    
    return ContainerInfo(
        container_name=container_name,
        ip_address=ip_address,
        host_id=host_id or "unknown"
    )

@app.get("/check/{container_name}", tags=["Monitoring"])
async def check_container_exists(container_name: str):
    """Check if a container name is already in use globally"""
    
    ip_address = r.hget("container_ips", container_name)
    host_id = r.hget("container_hosts", container_name)
    
    if ip_address:
        return {
            "exists": True,
            "container_name": container_name,
            "ip_address": ip_address,
            "host_id": host_id
        }
    else:
        return {
            "exists": False,
            "container_name": container_name
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=IPAM_HOST, port=IPAM_PORT)