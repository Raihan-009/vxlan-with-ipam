# VXLAN Container Cluster - System Architecture

## Overview

This document describes the architecture of a VXLAN-based container clustering solution that provides Docker Swarm-like functionality with centralized IP address management (IPAM) and cross-host container networking.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           VXLAN Container Cluster                           │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────┐         ┌──────────────────────────┐
│        HOST-1            │◄────────┤        HOST-2            │
│     (10.0.1.142)         │  VXLAN  │     (10.0.1.6)           │
│                          │  Tunnel │                          │
│  ┌─────────────────────┐ │         │                          │
│  │   IPAM Service      │ │         │                          │
│  │   (Redis + API)     │ │         │                          │
│  │   Port: 8000        │ │         │                          │
│  └─────────────────────┘ │         │                          │
│                          │         │                          │
│  ┌─────────────────────┐ │         │  ┌─────────────────────┐ │
│  │ Container Service   │ │         │  │ Container Service   │ │
│  │   (FastAPI)         │ │         │  │   (FastAPI)         │ │
│  │   Port: 8001        │ │         │  │   Port: 8001        │ │
│  └─────────────────────┘ │         │  └─────────────────────┘ │
│                          │         │                          │
│  ┌─────────────────────┐ │         │  ┌─────────────────────┐ │
│  │   Docker Engine     │ │         │  │   Docker Engine     │ │
│  │   Network: vxlan-net│ │         │  │   Network: vxlan-net│ │
│  │   Bridge: br-xxxxx  │ │         │  │   Bridge: br-xxxxx  │ │
│  └─────────────────────┘ │         │  └─────────────────────┘ │
│                          │         │                          │
│  ┌─────┐ ┌─────┐ ┌─────┐ │         │  ┌─────┐ ┌─────┐ ┌─────┐ │
│  │ C1  │ │ C2  │ │ C3  │ │         │  │ C4  │ │ C5  │ │ C6  │ │
│  └─────┘ └─────┘ └─────┘ │         │  └─────┘ └─────┘ └─────┘ │
└──────────────────────────┘         └──────────────────────────┘
```

## Component Architecture

### 1. Network Layer

```
┌─────────────────────────────────────────────────────────────────┐
│                      Network Architecture                       │
└─────────────────────────────────────────────────────────────────┘

Physical Network: 10.0.1.0/24
├── Host-1: 10.0.1.142
└── Host-2: 10.0.1.6

VXLAN Overlay Network: 172.20.0.0/16
├── Gateway: 172.20.0.1
├── VXLAN ID: 100
├── UDP Port: 4789
└── Container IP Range: 172.20.0.10 - 172.20.255.254

VXLAN Encapsulation:
┌─────────────────┐
│ Outer Ethernet  │ ← Physical host MACs
├─────────────────┤
│ Outer IP        │ ← Host IPs (10.0.1.142/40)
├─────────────────┤
│ Outer UDP       │ ← Port 4789
├─────────────────┤
│ VXLAN Header    │ ← VNI: 100
├─────────────────┤
│ Inner Ethernet  │ ← Container MACs
├─────────────────┤
│ Inner IP        │ ← Container IPs (172.20.0.x)
├─────────────────┤
│ Application     │ ← HTTP, SSH, etc.
└─────────────────┘
```

### 2. Service Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Service Architecture                       │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Client/User   │    │   Swagger UI    │    │  External APIs  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   IPAM Service  │    │Container Service│    │Container Service│
│   (Host-1 Only) │    │    (Host-1)     │    │    (Host-2)     │
│   Port: 8000    │    │   Port: 8001    │    │   Port: 8001    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Redis Database │    │  Docker Engine  │    │  Docker Engine  │
│   (Host-1)      │    │    (Host-1)     │    │    (Host-2)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 3. Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       Data Flow Architecture                    │
└─────────────────────────────────────────────────────────────────┘

Container Creation Flow:
┌─────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────┐
│  User   │───▶│ Container   │───▶│ IPAM        │───▶│ Redis   │
│ Request │    │ Service     │    │ Service     │    │Database │
└─────────┘    └─────────────┘    └─────────────┘    └─────────┘
     │               │                   │               │
     │         ┌─────▼─────┐       ┌─────▼─────┐         │
     │         │1. Validate│       │2. Check   │         │
     │         │   Name    │       │   Global  │         │
     │         │   Unique  │       │   Names   │         │
     │         └───────────┘       └───────────┘         │ 
     │               │                   │               │
     │         ┌─────▼─────┐       ┌─────▼─────┐    ┌────▼────┐
     │         │3. Request │       │4. Allocate│    │5. Store │
     │         │    IP     │       │    IP     │    │   Data  │
     │         └───────────┘       └───────────┘    └─────────┘
     │               │                   │               │
     │         ┌─────▼─────┐             |               │
     └────────▶│6. Create  │◄──────────────────────────-─┘
               │ Container │
               │ with IP   │
               └───────────┘

Container Communication Flow:
┌─────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────┐
│Container│───▶│   Docker    │───▶│    VXLAN    │───▶│Container│
│ Host-1  │    │   Bridge    │    │   Tunnel    │    │ Host-2  │
│172.20.10│    │ br-xxxxxx   │    │ vxlan0      │    │172.20.11│
└─────────┘    └─────────────┘    └─────────────┘    └─────────┘
```

## Technology Stack

### Core Technologies
- **VXLAN**: Virtual Extensible LAN for overlay networking
- **Docker**: Container runtime and networking
- **FastAPI**: REST API framework with automatic OpenAPI documentation
- **Redis**: In-memory database for IP address management
- **Python**: Primary programming language for services
- **Uvicorn**: ASGI server for FastAPI applications

### Network Components
- **Linux Bridge**: Docker bridge networking
- **iptables**: Network packet filtering and NAT
- **UDP**: Transport protocol for VXLAN encapsulation
- **Ethernet**: Layer 2 networking within containers

### Infrastructure
- **systemd**: Service management and auto-start
- **journalctl**: Centralized logging
- **cron**: Scheduled health checks and maintenance

## Security Model

### Network Security
```
┌─────────────────────────────────────────────────────────────────┐
│                      Security Architecture                      │
└─────────────────────────────────────────────────────────────────┘

Network Isolation:
┌─────────────────┐    ┌─────────────────┐
│  Physical Net   │    │  Container Net  │
│  10.0.1.0/24    │    │ 172.20.0.0/16   │
└─────────────────┘    └─────────────────┘
         │                       │
         └───── VXLAN Tunnel ────┘
              (Encrypted Optional)

Access Control:
- IPAM Service: Only accessible from cluster hosts
- Container Services: Host-specific access
- Redis: Local access only on Host-1
- Containers: Isolated by network namespace
```

### Service Security
- **API Authentication**: Can be extended with JWT/OAuth
- **Network Isolation**: Services only accessible within cluster
- **Container Isolation**: Docker security features
- **Resource Limits**: Configurable container resource constraints

## Scalability Considerations

### Horizontal Scaling
```
Current: 2-Host Cluster
┌────────┐    ┌────────┐
│ Host-1 │────│ Host-2 │
└────────┘    └────────┘

Extended: N-Host Cluster
┌────────┐    ┌────────┐    ┌────────┐    ┌────────┐
│ Host-1 │────│ Host-2 │────│ Host-3 │────│ Host-N │
└────────┘    └────────┘    └────────┘    └────────┘
     │           │           │           │
     └───────────┼───────────┼───────────┘
                 │           │
                IPAM Service (HA)
```

### Scaling Limits
- **VXLAN Limit**: 16M virtual networks (24-bit VNI)
- **Container IPs**: 65,534 containers per network (172.20.0.0/16)
- **Redis Performance**: 100K+ operations/second
- **Host Limits**: Limited by VXLAN multicast/unicast capabilities

## High Availability Options

### IPAM Service HA
```
Primary Setup:
┌────────────────┐
│    Host-1      │
│ ┌────────────┐ │
│ │IPAM + Redis│ │
│ └────────────┘ │
└────────────────┘

HA Setup (Future):
┌────────────────┐    ┌────────────────┐
│    Host-1      │    │    Host-3      │
│ ┌────────────┐ │    │ ┌────────────┐ │
│ │IPAM Primary│ │    │ │IPAM Standby│ │
│ │Redis Master│ │    │ │Redis Slave │ │
│ └────────────┘ │    │ └────────────┘ │
└────────────────┘    └────────────────┘
```

## Performance Characteristics

### Network Performance
- **Latency**: +0.1ms overhead from VXLAN encapsulation
- **Bandwidth**: ~95% of physical network bandwidth
- **Packet Size**: +50 bytes overhead from VXLAN headers

### Service Performance
- **Container Creation**: 2-5 seconds per container
- **IP Allocation**: <100ms per request
- **API Response**: <50ms for most operations
- **Database Operations**: <10ms for Redis operations

## Monitoring and Observability

### Built-in Monitoring
- Health check endpoints for all services
- Container and IP allocation statistics
- Network interface status monitoring
- Automated log rotation and retention

### External Integration Points
- **Prometheus**: Metrics collection endpoints available
- **Grafana**: Dashboard integration capability
- **ELK Stack**: Structured logging output
- **Alerting**: Service status and threshold monitoring

This architecture provides a robust, scalable foundation for multi-host container networking with centralized management and monitoring capabilities.
