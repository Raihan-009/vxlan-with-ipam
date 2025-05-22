# config.py
# /opt/vxlan-cluster/config.py
import os

# Network Configuration
NETWORK_SUBNET = "172.20.0.0/16"
NETWORK_START = "172.20.0.10"  # Starting IP for containers
NETWORK_END = "172.20.255.254"  # Ending IP for containers
GATEWAY_IP = "172.20.0.1"

# Redis Configuration
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0

# Service Configuration
IPAM_HOST = "0.0.0.0"
IPAM_PORT = 8000
CONTAINER_SERVICE_PORT = 8001

# Host Configuration
HOST1_IP = "10.0.1.142"
HOST2_IP = "10.0.1.6"

# Docker Configuration
DOCKER_NETWORK_NAME = "vxlan-net"
