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
