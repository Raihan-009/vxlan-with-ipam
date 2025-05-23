# Network Configuration
NETWORK_SUBNET = "172.20.0.0/16"
NETWORK_START = "172.20.0.10"
NETWORK_END = "172.20.255.254"
GATEWAY_IP = "172.20.0.1"

# Node IPs
IPAM_NODE_IP = "10.0.1.4"
HOST1_IP = "10.0.1.65"
HOST2_IP = "10.0.1.106"

# Ports
IPAM_PORT = 8000
CONTAINER_SERVICE_PORT = 8001
REDIS_PORT = 6379

# Redis Configuration (Docker internal)
REDIS_HOST = "redis"
REDIS_DB = 0

# Service Configuration
IPAM_HOST = "0.0.0.0"
DOCKER_NETWORK_NAME = "vxlan-net"

# IPAM Service URL
IPAM_SERVICE_URL = f"http://{IPAM_NODE_IP}:{IPAM_PORT}"