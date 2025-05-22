# /opt/vxlan-cluster/start_container_service.sh

#!/bin/bash
# start_container_service.sh

cd /opt/vxlan-cluster
source venv/bin/activate

echo "Starting Container Service on $(hostname)..."
echo "Docker status: $(systemctl is-active docker)"

# Check if Docker is running
if ! systemctl is-active --quiet docker; then
    echo "Starting Docker..."
    sudo systemctl start docker
fi

# Wait for IPAM service to be available (only check from Host-2)
if [ "$(hostname -I | grep -o '10\.0\.1\.6')" ]; then
    echo "Waiting for IPAM service on Host-1..."
    while ! curl -s http://10.0.1.142:8000/ > /dev/null; do
        echo "Waiting for IPAM service..."
        sleep 2
    done
    echo "IPAM service is available!"
fi

# Start Container service
python container_service.py
