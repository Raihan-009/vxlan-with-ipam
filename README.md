# VXLAN Container Cluster
**Multi-Host Docker Container Orchestration with Centralized IP Management**

## Overview

This project implements a distributed container orchestration system using VXLAN (Virtual Extensible LAN) technology to enable seamless communication between Docker containers across multiple physical hosts. The architecture features centralized IP address management (IPAM) with Redis backend for persistent state management.

### Key Features
- **Cross-host container communication** via VXLAN overlay network
- **Centralized IP allocation** with collision prevention
- **Persistent container registry** using Redis
- **RESTful API** for container lifecycle management
- **Network isolation** with overlay tunneling

---

## Architecture Overview

![cluster view](https://raw.githubusercontent.com/Raihan-009/vxlan-with-ipam/f3a90ce0624e6a6cc7524c8653b00ae257a2ba82/Assets/vxlan-cluster.svg)

The system consists of three main components:

### 1. **IPAM Service (Host 3)** - Centralized Control Plane
- **Purpose**: Manages IP address pool and container registry
- **Technology**: FastAPI + Redis
- **Network**: Management network (10.0.1.0/24)
- **Responsibilities**:
  - IP address allocation/deallocation
  - Container metadata storage
  - Cross-host service discovery

### 2. **Container Hosts (Host 1 & 2)** - Compute Nodes  
- **Purpose**: Run containers and manage local Docker networks
- **Technology**: Docker Engine + VXLAN networking
- **Networks**: 
  - Management: 10.0.1.0/24 (host communication)
  - Overlay: 172.20.0.0/16 (container communication)

### 3. **VXLAN Overlay Network** - Data Plane
- **VNI**: 100 (Virtual Network Identifier)
- **Transport**: UDP port 4789
- **Subnet**: 172.20.0.0/16 with /24 allocation per host

---

## Network Flow & Communication

![container lifecycle](https://raw.githubusercontent.com/Raihan-009/vxlan-with-ipam/f3a90ce0624e6a6cc7524c8653b00ae257a2ba82/Assets/container-creation.svg)

### Container Creation Workflow

The container creation process follows a systematic approach:

1. **API Request**: Client sends container creation request to host
2. **Name Validation**: System checks container name availability via IPAM
3. **IP Allocation**: IPAM service assigns available IP from pool
4. **Container Deployment**: Docker creates container with assigned IP
5. **Network Attachment**: Container connects to VXLAN overlay network

### Redis Operations During IP Allocation

The IPAM service uses Redis data structures for efficient IP management:

- **`available_ips` (Set)**: Pool of unallocated IP addresses
- **`allocated_ips` (Set)**: Currently assigned IP addresses  
- **`container_ips` (Hash)**: Container name → IP mapping
- **`container_hosts` (Hash)**: Container → Host mapping

---

## Technical Deep Dive

![protocol details](https://raw.githubusercontent.com/Raihan-009/vxlan-with-ipam/f3a90ce0624e6a6cc7524c8653b00ae257a2ba82/Assets/vxlan-stack.svg)

### VXLAN Encapsulation Process

When containers communicate across hosts, packets undergo VXLAN encapsulation:

1. **Container Layer**: Application generates packet (e.g., nginx1 → nginx2)
2. **Docker Bridge**: Routes packet to VXLAN interface based on destination
3. **VXLAN Encapsulation**: Wraps inner packet with VXLAN header (VNI: 100)
4. **UDP Transport**: Encapsulates VXLAN packet in UDP (port 4789)
5. **Physical Network**: Transmits over management network to destination host
6. **Decapsulation**: Destination host extracts inner packet and forwards to target container

### Network Stack Layers

Each host maintains a complete network stack:

- **Physical Interface** (eth0): Management network connectivity
- **VXLAN Interface** (vxlan0): Overlay network endpoint
- **Docker Bridge** (br-xxxxx): Container network bridge
- **Container Network**: Isolated container networking

---

## Prerequisites

- **Operating System**: Linux with kernel 3.7+ (VXLAN support)
- **Docker**: Version 20.10+ with bridge networking
- **Network Connectivity**: All hosts reachable on management network
- **System Access**: Root/sudo privileges for network configuration
- **Firewall**: UDP port 4789 open between hosts

---

## Quick Start Guide

### Step 1: Deploy IPAM Service (Host 3)
```bash
# Clone repository and setup IPAM
cd /opt && git clone <repository>
cd vxlan-cluster/ipam
docker-compose up -d --build

# Verify IPAM service
curl http://localhost:8000/stats
```

### Step 2: Setup Container Host 1
```bash
# Setup application files
cd /opt/vxlan-cluster/host1
docker-compose up -d --build

# Configure VXLAN network
sudo ./setup_vxlan_host1.sh

# Verify container service
curl http://localhost:8001/health
```

### Step 3: Setup Container Host 2
```bash
# Setup application files  
cd /opt/vxlan-cluster/host2
docker-compose up -d --build

# Configure VXLAN network
sudo ./setup_vxlan_host2.sh

# Verify container service
curl http://localhost:8001/health
```

---

## Testing & Validation

### Create Test Containers
```bash
# Deploy nginx container on Host 1
curl -X POST "http://10.0.1.142:8001/create_container?container_name=test1&image=nginx:alpine"

# Deploy nginx container on Host 2
curl -X POST "http://10.0.1.6:8001/create_container?container_name=test2&image=nginx:alpine"
```

### Verify Cross-Host Communication
```bash
# Check container IP assignments
curl http://10.0.1.100:8000/containers

# Test network connectivity
docker exec test1 ping -c 3 <test2_ip>
docker exec test2 ping -c 3 <test1_ip>

# Test HTTP communication
docker exec test1 curl http://<test2_ip>:80
```

### Expected Outcomes

- ✅ **IP Allocation**: Each container receives unique IP from centralized pool
- ✅ **Cross-Host Ping**: Containers can ping across physical host boundaries  
- ✅ **Service Discovery**: Containers discoverable via IPAM registry
- ✅ **Network Isolation**: Container traffic encapsulated in VXLAN tunnel
- ✅ **Persistent State**: Container mappings survive service restarts

---

## API Reference

### IPAM Service Endpoints
```http
GET  /stats              # System statistics
GET  /containers         # List all containers  
POST /allocate           # Request IP allocation
POST /deallocate         # Release IP address
GET  /check/{name}       # Check name availability
```

### Container Service Endpoints  
```http
GET  /health                    # Service health check
POST /create_container          # Deploy new container
GET  /containers               # List local containers
DELETE /container/{name}       # Remove container
```

---

## Troubleshooting Guide

### Network Connectivity Issues
```bash
# Check VXLAN interface status
ip link show vxlan0
bridge fdb show dev vxlan0

# Verify Docker network
docker network inspect vxlan-net

# Test container networking
docker exec <container> ip route
docker exec <container> ping <gateway>
```

### IPAM Service Issues
```bash
# Monitor Redis operations
docker exec -it vxlan-redis redis-cli MONITOR

# Check available IP pool
docker exec -it vxlan-redis redis-cli SCARD available_ips

# Verify container mappings
docker exec -it vxlan-redis redis-cli HGETALL container_ips
```

### Performance Monitoring
```bash
# Network traffic analysis
tcpdump -i vxlan0 -n

# Container resource usage
docker stats

# VXLAN packet inspection
tcpdump -i eth0 port 4789 -n
```

---

## Configuration Parameters

### Network Configuration
- **Management Network**: `10.0.1.0/24`
- **Container Network**: `172.20.0.0/16`  
- **VXLAN VNI**: `100`
- **UDP Port**: `4789`

### Service Ports
- **IPAM Service**: `8000`
- **Container Service**: `8001`  
- **Redis**: `6379` (internal)

### IP Pool Management
- **Total IPs**: 65,534 addresses
- **Available Pool**: Dynamically managed via Redis
- **Allocation Strategy**: First-available from set

---

### Scalability
- Consider IP pool exhaustion at scale
- Implement container garbage collection
- Monitor network bandwidth utilization
- Plan for multi-datacenter deployments
