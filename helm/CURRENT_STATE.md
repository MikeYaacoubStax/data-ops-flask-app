# Current State - NoSQLBench Kubernetes Demo

## 🎯 Current Working Configuration

### Test Environment
- **Platform**: minikube
- **Resources**: 4 CPUs, 8GB RAM, 20GB disk
- **Kubernetes**: Latest version via minikube
- **Image**: `nosqlbench-webapp:v1.0.0` (built locally)

### Database Endpoints (test-values.yaml)
```yaml
databases:
  cassandra:
    enabled: true
    host: "3.91.36.147"
    port: 9042
    localdc: "datacenter1"
  
  opensearch:
    enabled: true
    host: "3.91.36.147"
    port: 9200
  
  presto:
    enabled: true
    host: "3.91.36.147"
    port: 8080
    user: "testuser"
```

### VictoriaMetrics
- **Local Docker**: `docker run -p 8428:8428 victoriametrics/victoria-metrics`
- **Minikube Access**: `http://host.minikube.internal:8428`

## 🔧 Key Fixes Applied

### 1. RBAC Permissions
- **Issue**: Service account couldn't create/patch ConfigMaps
- **Fix**: Added `create`, `update`, `patch`, `delete` permissions for ConfigMaps in `templates/role.yaml`

### 2. NoSQLBench Command
- **Issue**: Jobs failing with "executable not found" (`nb5`, `./nb`)
- **Fix**: Use `args` instead of `command` to work with image's entrypoint

### 3. Label Conflicts
- **Issue**: NoSQLBench label conflicts causing "Can't overlap label keys" errors
- **Fix**: Removed `--add-labels` from setup jobs, only use for benchmark jobs

### 4. Resource Limits
- **Issue**: OutOfMemoryError in LWT workloads with 1Gi limit
- **Fix**: Increased to 4Gi memory limit, 2 CPU cores
- **Implementation**: Dynamic resource configuration via environment variables

### 5. Job Naming
- **Issue**: Kubernetes job names with underscores/dots (invalid)
- **Fix**: Convert underscores to hyphens in job names

## 🚀 Current Deployment Commands

### Quick Deploy
```bash
cd helm
./setup-minikube.sh
```

### Manual Deploy
```bash
# Set minikube docker context
eval $(minikube docker-env)

# Build webapp image
cd docker && docker build -t nosqlbench-webapp:v1.0.0 .

# Install chart
cd .. && helm install nosqlbench-demo . -f test-values.yaml

# Access UI
minikube service nosqlbench-demo
```

### Update After Code Changes
```bash
cd helm
eval $(minikube docker-env)
cd docker && docker build --no-cache -t nosqlbench-webapp:v1.0.0 .
cd .. && helm upgrade nosqlbench-demo . -f test-values.yaml
kubectl rollout status deployment/nosqlbench-demo
```

## 📊 Working Features

### ✅ Web Interface
- **URL**: `minikube service nosqlbench-demo --url`
- **Material Design**: Clean, responsive UI
- **Real-time Updates**: WebSocket every 2 seconds
- **Job Management**: Start, stop, update throughput

### ✅ Setup Process
- **Sequential Execution**: drop → schema → rampup
- **Progress Tracking**: Real-time progress bar
- **Error Handling**: Proper error display and recovery

### ✅ Benchmark Management
- **Dynamic Jobs**: Create/delete jobs for throughput changes
- **Resource Allocation**: 4Gi memory, 2 CPU cores
- **Monitoring**: Real-time runtime display

### ✅ State Management
- **ConfigMap Storage**: No external dependencies
- **Persistence**: Setup completion and running job tracking
- **Recovery**: Survives webapp restarts

## 🔍 Monitoring Commands

### Check Status
```bash
# Overall status
kubectl get all -l app.kubernetes.io/instance=nosqlbench-demo

# Job status
kubectl get jobs -l job-type=setup
kubectl get jobs -l job-type=benchmark

# Webapp logs
kubectl logs -l app.kubernetes.io/name=nosqlbench-demo --tail=20

# Job logs
kubectl logs -l job-type=setup --tail=50
```

### Debug Issues
```bash
# Check events
kubectl get events --sort-by=.metadata.creationTimestamp

# Describe failing pods
kubectl describe pod <pod-name>

# Check resource usage
kubectl top pods
kubectl top nodes

# Test database connectivity
kubectl run test-conn --image=busybox --rm -it --restart=Never -- nc -zv 3.91.36.147 9042
```

## 🎯 Known Working Workloads

### Cassandra
- **cassandra_sai**: Secondary Index workload
- **cassandra_lwt**: Lightweight Transactions (requires 4Gi memory)

### OpenSearch
- **opensearch_basic**: Basic search operations
- **opensearch_vector**: Vector search
- **opensearch_bulk**: Bulk operations

### Presto
- **presto_analytics**: Analytics queries
- **presto_ecommerce**: E-commerce transactions

## 🔧 Current Resource Configuration

### NoSQLBench Jobs
```yaml
resources:
  requests:
    cpu: 200m
    memory: 1Gi
  limits:
    cpu: 2000m
    memory: 4Gi
```

### Webapp
```yaml
resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: 500m
    memory: 512Mi
```

## 📝 Next Steps (if needed)

### Potential Enhancements
1. **Grafana Integration**: Dashboard for metrics visualization
2. **Job History**: Persistent storage for completed job results
3. **Multi-namespace**: Support for multiple database namespaces
4. **Authentication**: RBAC for web interface access
5. **Scaling**: Horizontal pod autoscaling for webapp

### Production Readiness
1. **Image Registry**: Push to private registry
2. **Ingress**: Configure proper ingress controller
3. **TLS**: Enable HTTPS for web interface
4. **Monitoring**: Integrate with Prometheus/Grafana
5. **Backup**: ConfigMap backup strategy

---

**Last Updated**: June 11, 2025  
**Working Status**: ✅ Fully Functional  
**Test Environment**: minikube with external databases
