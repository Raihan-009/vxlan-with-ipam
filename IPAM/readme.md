# Host 3 (IPAM Node) - 10.0.1.4

## Files Needed:

    /opt/vxlan-cluster/
    ├── config.py               # Same as IPAM host
    ├── ipam_service.py
    ├── requirements.txt        # Same as IPAM host
    ├── docker-compose.yml
    └── Dockerfile

## Commands to Run:


### 1. Create directory
```
mkdir -p /opt/vxlan-cluster
cd /opt/vxlan-cluster
```

### 2. Create all files (From IPAM Folder)

### 3. Build and start container service
```
docker-compose up -d --build
```

### 4. Verify service
```
curl http://localhost:8000/
curl http://localhost:8000/stats
```