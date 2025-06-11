# NoSQLBench Kubernetes Demo - Helm Chart

A complete Kubernetes-native solution for running NoSQLBench workloads with a modern web interface.

## 🚀 Overview

This Helm chart deploys a comprehensive NoSQLBench management system that includes:

- **Custom Web Application** with Material Design UI for job management
- **Kubernetes Job Manager** for dynamic NoSQLBench workload execution
- **Real-time Monitoring** with WebSocket updates and progress tracking
- **State Management** using Kubernetes ConfigMaps
- **Multi-Database Support** for Cassandra, OpenSearch, and Presto/Trino

## ✅ Current Status

**All Phases Complete:**
- ✅ **Phase 1**: Core Infrastructure implemented
- ✅ **Phase 2**: Job Management Logic implemented  
- ✅ **Phase 3**: Enhanced User Interface with Material Design

## 🏗️ Architecture

### Components

1. **Web Application** (`docker/app.py`)
   - Flask-based REST API and WebSocket server
   - Material Design UI with real-time updates
   - Kubernetes client integration for job management

2. **Job Manager** (`docker/services/k8s_job_manager.py`)
   - Dynamic Kubernetes Job creation and management
   - Sequential setup phase execution
   - Benchmark job lifecycle management
   - Resource configuration and monitoring

3. **State Manager** (`docker/services/k8s_state_manager.py`)
   - ConfigMap-based state persistence
   - Setup completion tracking
   - Running benchmark state management

4. **Configuration Manager** (`docker/services/config_manager.py`)
   - Database connection configuration
   - Workload definition management
   - Metrics endpoint configuration

### Workloads Supported

- **Cassandra**: SAI (Secondary Index), LWT (Lightweight Transactions)
- **OpenSearch**: Basic search, Vector search, Bulk operations
- **Presto/Trino**: Analytics queries, E-commerce transactions

## 🛠️ Installation

### Prerequisites

- Kubernetes cluster (tested with minikube)
- Helm 3.x
- Docker (for building the webapp image)
- Access to target databases (Cassandra, OpenSearch, Presto)

### Quick Start with Minikube

1. **Start minikube and build the image:**
   ```bash
   cd helm
   ./setup-minikube.sh
   ```

2. **Or manual installation:**
   ```bash
   # Start minikube
   minikube start --cpus=4 --memory=8192 --disk-size=20g
   
   # Build webapp image
   eval $(minikube docker-env)
   cd docker && docker build -t nosqlbench-webapp:v1.0.0 .
   
   # Install chart
   cd .. && helm install nosqlbench-demo . -f test-values.yaml
   
   # Access the UI
   minikube service nosqlbench-demo
   ```

### Production Installation

1. **Build and push the webapp image:**
   ```bash
   cd docker
   docker build -t your-registry.com/nosqlbench-webapp:v1.0.0 .
   docker push your-registry.com/nosqlbench-webapp:v1.0.0
   ```

2. **Install with custom values:**
   ```bash
   helm install nosqlbench-demo . \
     --set webapp.image.repository=your-registry.com/nosqlbench-webapp \
     --set webapp.image.tag=v1.0.0 \
     --set databases.cassandra.enabled=true \
     --set databases.cassandra.host=cassandra.example.com \
     --set databases.opensearch.enabled=true \
     --set databases.opensearch.host=opensearch.example.com \
     --set metrics.endpoint=http://victoriametrics.monitoring.svc.cluster.local:8428
   ```

## ⚙️ Configuration

### Database Configuration

```yaml
databases:
  cassandra:
    enabled: true
    host: "cassandra.example.com"
    port: 9042
    localdc: "datacenter1"
    # Optional authentication
    username: ""
    password: ""
  
  opensearch:
    enabled: true
    host: "opensearch.example.com"
    port: 9200
    # Optional authentication
    username: ""
    password: ""
  
  presto:
    enabled: true
    host: "presto.example.com"
    port: 8080
    user: "testuser"
    catalog: "memory"
```

### Resource Configuration

```yaml
nosqlbench:
  resources:
    limits:
      cpu: 2000m      # 2 CPU cores
      memory: 4Gi     # 4GB RAM (important for LWT workloads)
    requests:
      cpu: 200m
      memory: 1Gi
```

### Web Application Configuration

```yaml
webapp:
  image:
    repository: "nosqlbench-webapp"
    tag: "v1.0.0"
    pullPolicy: Never  # For local development
  
  service:
    type: NodePort     # Use LoadBalancer for production
    port: 80
  
  autoSetup: false     # Set to true for automatic setup on install
```

## 🎯 Usage

### Web Interface

1. **Access the UI:**
   ```bash
   # Get service URL
   kubectl get service nosqlbench-demo
   # Or with minikube
   minikube service nosqlbench-demo
   ```

2. **Setup Workloads:**
   - Click "Run Setup" to prepare workloads for benchmarking
   - Monitor progress with the real-time progress bar
   - Setup runs sequentially: drop → schema → rampup

3. **Manage Benchmarks:**
   - **Start**: Click "Start" button with desired cycle rate (1-10000)
   - **Update Throughput**: Modify cycle rate and click "Update"
   - **Stop**: Click "Stop" to terminate running benchmarks
   - **Monitor**: View real-time runtime and status updates

### Command Line Management

```bash
# Monitor jobs
kubectl get jobs -l app.kubernetes.io/instance=nosqlbench-demo

# View setup job logs
kubectl logs -l job-type=setup

# View benchmark job logs
kubectl logs -l job-type=benchmark

# Check webapp logs
kubectl logs -l app.kubernetes.io/name=nosqlbench-demo

# Scale resources if needed
kubectl patch deployment nosqlbench-demo -p '{"spec":{"template":{"spec":{"containers":[{"name":"nosqlbench-demo","resources":{"limits":{"memory":"8Gi"}}}]}}}}'
```

## 🔧 Troubleshooting

### Common Issues

1. **OutOfMemoryError in NoSQLBench jobs:**
   ```bash
   # Increase memory limits in values.yaml
   nosqlbench:
     resources:
       limits:
         memory: 8Gi  # Increase from 4Gi
   ```

2. **Jobs failing with "executable not found":**
   - Ensure using correct NoSQLBench image version
   - Check that jobs use `args` instead of `command`

3. **State management errors (403 Forbidden):**
   - Verify RBAC permissions for ConfigMap access
   - Check service account has proper roles

4. **Database connection issues:**
   - Verify database hosts are accessible from cluster
   - Check firewall rules and network policies
   - Validate credentials if authentication is enabled

5. **Label conflicts in NoSQLBench:**
   - Ensure setup jobs don't include `--add-labels` parameters
   - Check job manager removes conflicting labels for setup phases

### Debug Commands

```bash
# Check pod status
kubectl describe pod -l app.kubernetes.io/name=nosqlbench-demo

# View events
kubectl get events --sort-by=.metadata.creationTimestamp

# Check job specifications
kubectl get job <job-name> -o yaml

# Test database connectivity
kubectl run test-db --image=busybox --rm -it --restart=Never -- nc -zv <db-host> <db-port>

# Check resource usage
kubectl top pods
kubectl top nodes
```

## 📊 Monitoring

### Metrics Integration

The system integrates with VictoriaMetrics for benchmark metrics:

```yaml
metrics:
  endpoint: "http://victoriametrics.monitoring.svc.cluster.local:8428"
```

### Job Monitoring

- **Setup Jobs**: Monitor with `kubectl get jobs -l job-type=setup`
- **Benchmark Jobs**: Monitor with `kubectl get jobs -l job-type=benchmark`
- **Web Interface**: Real-time status updates every 2 seconds

## 🔄 Development

### Building Custom Images

```bash
# Build webapp image
cd docker
docker build -t nosqlbench-webapp:dev .

# Test locally
docker run -p 5000:5000 nosqlbench-webapp:dev
```

### Modifying Workloads

1. Edit workload definitions in `values.yaml`
2. Update ConfigMap: `helm upgrade nosqlbench-demo . -f values.yaml`
3. Restart webapp: `kubectl rollout restart deployment/nosqlbench-demo`

### Key Files

- `docker/app.py` - Main Flask application
- `docker/services/k8s_job_manager.py` - Job management logic (key method: `_build_job_spec`)
- `docker/services/k8s_state_manager.py` - State persistence
- `docker/templates/index.html` - Material Design UI
- `templates/` - Kubernetes resource templates
- `values.yaml` - Configuration values

## 📝 Implementation Notes

### Resource Requirements
- **Memory**: LWT workloads require at least 4Gi memory
- **CPU**: 2 cores recommended for complex workloads
- **Storage**: Minimal, uses ConfigMaps for state

### Database Access
- Ensure databases are accessible from Kubernetes pods
- Use service discovery for in-cluster databases
- Configure proper network policies if required

### State Management
- Uses ConfigMaps for persistence (no external dependencies)
- State includes setup completion and running benchmark tracking
- Automatic cleanup of completed jobs via TTL

### Real-time Updates
- WebSocket connection provides live status updates
- Updates every 2 seconds without page refresh
- Graceful degradation if WebSocket fails

## 🚀 Production Considerations

1. **Image Registry**: Push webapp image to private registry
2. **Resource Limits**: Adjust based on workload requirements
3. **Monitoring**: Integrate with existing monitoring stack
4. **Security**: Configure network policies and pod security contexts
5. **Backup**: ConfigMap state can be backed up with cluster backups

## 🤝 Contributing

To extend functionality:

1. **Add New Workloads**: Update `workloadDefinitions` in `values.yaml`
2. **Add Database Support**: Extend job manager with new driver logic
3. **UI Enhancements**: Modify `docker/templates/index.html`
4. **API Extensions**: Add endpoints in `docker/app.py`

---

**Status**: Production Ready ✅
**Last Updated**: June 2025
**Version**: 1.0.0
