# /opt/vxlan-cluster/start_ipam.sh

#!/bin/bash


cd /opt/vxlan-cluster
source venv/bin/activate

echo "Starting IPAM Service on Host-1..."
echo "Redis status: $(systemctl is-active redis)"

# Check if Redis is running
if ! systemctl is-active --quiet redis; then
    echo "Starting Redis..."
    sudo systemctl start redis
fi

# Start IPAM service
python ipam_service.py
