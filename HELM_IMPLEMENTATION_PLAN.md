# NoSQLBench Kubernetes Helm Chart Implementation Plan

## Overview
Create a Helm chart that replicates the functionality of both the Docker Compose and Flask application implementations, but simplified for Kubernetes deployment. The chart will deploy a web interface that manages NoSQLBench workloads as Kubernetes Jobs.

## Architecture Components

### 1. Web Application (Deployment)
- **Image**: Custom Flask application (similar to current app.py)
- **Purpose**: Provides web UI for managing benchmarks
- **Features**:
  - Setup workloads UI with progress tracking
  - Start/stop benchmark jobs
  - Real-time throughput adjustment
  - Job status monitoring

### 2. NoSQLBench Jobs (Kubernetes Jobs)
- **Setup Jobs**: One-time jobs for each workload setup phase
- **Benchmark Jobs**: Long-running jobs for benchmark execution
- **Image**: `nosqlbench/nosqlbench:5.21.8-preview`

### 3. RBAC & ServiceAccount
- **Permissions**: Create, read, update, delete Jobs
- **Scope**: Namespace-scoped for security

## Helm Chart Structure

```
helm/
├── Chart.yaml
├── values.yaml
├── templates/
│   ├── deployment.yaml           # Web application
│   ├── service.yaml             # Web service
│   ├── ingress.yaml             # Optional ingress
│   ├── serviceaccount.yaml      # RBAC for job management
│   ├── role.yaml                # Kubernetes permissions
│   ├── rolebinding.yaml         # Bind role to service account
│   ├── configmap.yaml           # Workload configurations
│   ├── secret.yaml              # Database credentials (optional)
│   └── _helpers.tpl             # Template helpers
├── workloads/                   # NoSQLBench workload definitions
│   ├── sai_longrun.yaml
│   ├── lwt_longrun.yaml
│   ├── opensearch_basic_longrun.yaml
│   ├── opensearch_bulk_longrun.yaml
│   └── jdbc_ecommerce_longrun.yaml
└── docker/
    └── Dockerfile               # Custom web app image
```

## Key Values Configuration

### Database Endpoints (Required)
```yaml
databases:
  cassandra:
    enabled: true
    host: "cassandra.example.com"
    port: 9042
    localdc: "datacenter1"
  
  opensearch:
    enabled: true
    host: "opensearch.example.com"
    port: 9200
  
  presto:
    enabled: true
    host: "presto.example.com"
    port: 8080
    user: "testuser"

# VictoriaMetrics endpoint for metrics
metrics:
  endpoint: "http://victoriametrics.monitoring.svc.cluster.local:8428"

# Web application configuration
webapp:
  image:
    repository: "nosqlbench-webapp"
    tag: "latest"
  service:
    type: ClusterIP
    port: 80
  
  # Auto-setup on install
  autoSetup: true
```

## Implementation Phases

### Phase 1: Core Infrastructure
1. **Helm Chart Skeleton**
   - Chart.yaml with metadata
   - Basic values.yaml structure
   - Template helpers

2. **RBAC Setup**
   - ServiceAccount for job management
   - Role with Job CRUD permissions
   - RoleBinding

3. **Web Application Deployment**
   - Deployment template
   - Service template
   - ConfigMap for workload definitions

### Phase 2: Job Management Logic
1. **Custom Web Application**
   - Flask app with Kubernetes client
   - Job creation/monitoring logic
   - Real-time status updates via WebSocket

2. **Setup Job Templates**
   - Dynamic Job generation for setup phases
   - Sequential execution (drop → schema → rampup)
   - Progress tracking

3. **Benchmark Job Templates**
   - Long-running Job creation
   - Throughput adjustment via Job replacement
   - Status monitoring

### Phase 3: User Interface
1. **Setup Phase UI**
   - "Setting up workloads for benchmarking - Ramping up" display
   - Progress indicators for each workload
   - Conditional display based on enabled databases

2. **Benchmark Control UI**
   - Start/stop benchmark buttons
   - Throughput adjustment controls
   - Real-time status updates
   - Job logs access

## Technical Implementation Details

### Web Application Components

#### 1. Kubernetes Client Integration
```python
from kubernetes import client, config
from kubernetes.client.rest import ApiException

class KubernetesJobManager:
    def __init__(self, namespace):
        config.load_incluster_config()  # Load from pod
        self.batch_v1 = client.BatchV1Api()
        self.namespace = namespace
    
    def create_setup_job(self, workload_name, phase, db_config):
        # Create Job spec for setup phase
        pass
    
    def create_benchmark_job(self, workload_name, cycle_rate, db_config):
        # Create Job spec for benchmark
        pass
```

#### 2. Job Template Generation
- Dynamic Job specs based on workload configuration
- Environment variable injection for database connections
- Volume mounts for workload files and results

#### 3. Status Monitoring
- Watch Job status changes
- WebSocket updates to frontend
- Log aggregation from Job pods

### Setup Process Flow
1. **Chart Installation**
   - Deploy web application
   - Create RBAC resources
   - Mount workload configurations

2. **Auto-Setup Execution** (if enabled)
   - Detect enabled databases from values
   - Create setup Jobs for each workload sequentially
   - Monitor completion status

3. **UI State Management**
   - Display setup progress
   - Enable benchmark controls after setup completion
   - Real-time status updates

### Benchmark Management
1. **Job Creation**
   - Generate unique Job names
   - Set appropriate resource limits
   - Configure metrics endpoint

2. **Throughput Adjustment**
   - Delete existing Job
   - Create new Job with updated cycle rate
   - Preserve runtime continuity in metrics

3. **Cleanup**
   - Automatic Job cleanup after completion
   - Configurable retention policy

## Security Considerations
- Namespace-scoped RBAC (no cluster-wide permissions)
- Optional secret management for database credentials
- Network policies for pod-to-pod communication
- Resource limits and quotas

## Monitoring Integration
- All NoSQLBench jobs report to specified VictoriaMetrics endpoint
- No built-in monitoring infrastructure (simplified)
- Compatible with existing Grafana dashboards

## Installation & Usage

### Installation
```bash
helm install nosqlbench-demo ./helm \
  --set databases.cassandra.host=cassandra.example.com \
  --set databases.opensearch.host=opensearch.example.com \
  --set metrics.endpoint=http://victoriametrics:8428
```

### Access
```bash
kubectl port-forward svc/nosqlbench-demo 8080:80
# Open http://localhost:8080
```

## Next Steps
1. Review and approve this implementation plan
2. Create Helm chart skeleton
3. Develop custom web application with Kubernetes integration
4. Implement Job management logic
5. Create user interface
6. Testing and validation

This implementation provides the same functionality as the Docker and Flask versions but optimized for Kubernetes environments with simplified infrastructure requirements.
