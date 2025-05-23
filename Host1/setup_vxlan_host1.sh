#!/bin/bash
set -e

echo "🌐 Setting up VXLAN on Host 1 (10.0.1.142)..."

# Host configuration
LOCAL_IP="10.0.1.65"
REMOTE_IP="10.0.1.106"  # Host 2
VXLAN_ID=100
VXLAN_PORT=4789
DOCKER_SUBNET="172.20.0.0/16"
DOCKER_GATEWAY="172.20.0.1"

# 1. Create Docker network
echo "📡 Creating Docker bridge network..."
docker network create \
  --driver bridge \
  --subnet=$DOCKER_SUBNET \
  --gateway=$DOCKER_GATEWAY \
  vxlan-net 2>/dev/null || echo "Network already exists"

# 2. Create VXLAN interface to Host 2
echo "🔗 Creating VXLAN tunnel to Host 2 ($REMOTE_IP)..."
sudo ip link del vxlan0 2>/dev/null || true  # Remove if exists
sudo ip link add vxlan0 type vxlan \
  id $VXLAN_ID \
  remote $REMOTE_IP \
  dstport $VXLAN_PORT \
  dev eth0

# 3. Activate VXLAN interface
echo "⚡ Activating VXLAN interface..."
sudo ip link set vxlan0 up

# 4. Get Docker bridge ID and connect VXLAN
echo "🔌 Connecting VXLAN to Docker bridge..."
BRIDGE_ID=$(docker network inspect vxlan-net -f '{{.Id}}' | cut -c1-12)
sudo ip link set vxlan0 master br-$BRIDGE_ID

# 5. Verify setup
echo "✅ VXLAN setup complete!"
echo "🔍 Network verification:"
ip link show vxlan0
bridge link show vxlan0

echo "🎯 Ready to create containers on VXLAN network!"