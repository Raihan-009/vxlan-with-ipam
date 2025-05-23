# Host 1 (Container Node) - 10.0.1.65

## Files Needed:

    /opt/vxlan-cluster/
    ├── config.py               # Same as IPAM host
    ├── container_service.py
    ├── requirements.txt        # Same as IPAM host
    ├── docker-compose.yml
    └── Dockerfile

## Commands to Run:


### 1. Create directory
```
mkdir -p /opt/vxlan-cluster
cd /opt/vxlan-cluster
```

### 2. Create all files (From Host1 Folder)

### 3. Wait for IPAM service to be ready
```bash
while ! curl -s http://10.0.1.4:8000/ > /dev/null; do
    echo "Waiting for IPAM service..."
    sleep 2
done
```

### 4. Build and start container service
```
docker-compose up -d --build
```

### 5. Verify service
```
curl http://localhost:8001/health
```