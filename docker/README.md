# NoSQLBench Docker Infrastructure

This directory contains a comprehensive Docker-based infrastructure for running NoSQLBench workloads with full monitoring capabilities. The infrastructure is designed to support setup and run phases of multiple database workloads with configurable throughput parameters.

## 🏗️ Architecture Overview

The infrastructure consists of four main components:

### 1. Monitoring Stack (`docker-compose.monitoring.yml`)
- **Grafana**: Visualization and dashboards (port 3000)
- **VictoriaMetrics**: Time series database for NoSQLBench metrics (port 8428)
- **Graphite**: Metrics collection for OpenSearch Benchmark (port 8081)
- **Node Exporter**: System metrics collection (port 9100)

### 2. Database Stack (`docker-compose.databases.yml`)
- **Cassandra 4.1**: CQL database with datacenter1 configuration (port 9042)
- **OpenSearch 2.11**: Search engine with security disabled (port 9200)
- **Trino**: SQL query engine with memory and PostgreSQL connectors (port 8080)
- **PostgreSQL**: Supporting database for Trino testing (port 5432)

### 3. NoSQLBench Setup Stack (`docker-compose.nosqlbench-setup.yml`)
- Dedicated containers for running setup phases of each workload
- 10-minute timeout for setup operations (user preference)
- Automatic dependency waiting and health checks

### 4. NoSQLBench Run Stack (`docker-compose.nosqlbench-run.yml`)
- Dedicated containers for running benchmark phases
- Configurable throughput and thread parameters
- Integrated metrics collection to VictoriaMetrics

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose installed
- At least 8GB RAM available for containers
- Ports 3000, 8428, 8081, 9042, 9200, 8080, 5432 available

### ✅ **NoSQLBench Preview Image with Full Driver Support**

**The Docker infrastructure now uses `nosqlbench/nosqlbench:5.21.8-preview` with complete driver support.**

**What's Included:**
- All standard NoSQLBench drivers (CQL, HTTP, etc.)
- OpenSearch driver for search workloads
- JDBC driver for Presto/Trino workloads
- No custom builds or local installations required

**Key Benefits:**
- **No local nb5 command needed** - everything runs in Docker containers
- **All workloads supported** - Cassandra, OpenSearch, and Presto/Trino
- **Simplified setup** - just Docker and Docker Compose required
- **Consistent environment** - same image across all components

**Verification:**
```bash
# Test the preview image
docker run --rm nosqlbench/nosqlbench:5.21.8-preview nb5 --version
docker run --rm nosqlbench/nosqlbench:5.21.8-preview nb5 --list-drivers
```

### 1. Start Complete Infrastructure
```bash
cd docker
./manage.sh start all
```

This will start:
- Monitoring stack (Grafana, VictoriaMetrics, Graphite)
- Database stack (Cassandra, OpenSearch, Trino, PostgreSQL)

### 2. Access Services
- **Grafana**: http://localhost:3000 (admin/admin)
- **VictoriaMetrics**: http://localhost:8428
- **Graphite**: http://localhost:8081
- **OpenSearch**: http://localhost:9200
- **Trino**: http://localhost:8080

### 3. Run Workload Setup
```bash
# Setup all workloads
./manage.sh setup

# Setup specific workload
./manage.sh setup cassandra-sai
```

### 4. Run Benchmarks

**All workloads now supported via Docker containers:**
```bash
# Run all benchmarks
./manage.sh run

# Run specific benchmarks
./manage.sh run cassandra-sai
./manage.sh run opensearch-basic
./manage.sh run presto-analytics

# Or use Docker Compose directly
docker-compose -f docker-compose.nosqlbench-run.yml --profile run up -d
```

**Optional: Local nb5 script (for advanced users)**
```bash
# The run-local-nb5.sh script is still available for direct command execution
./run-local-nb5.sh check
./run-local-nb5.sh setup-opensearch-basic
./run-local-nb5.sh run-presto-analytics
```

## 📊 Supported Workloads

### Cassandra Workloads
| Workload | Description | Setup Phases | Run Phase | Default Throughput | Docker Support |
|----------|-------------|--------------|-----------|-------------------|----------------|
| **cassandra-sai** | Storage Attached Index queries with ALLOW FILTERING | schema, rampup | sai_reads | 1,000 ops/sec | ✅ Full |
| **cassandra-lwt** | Lightweight Transactions | schema, truncating, sharding, lwt_load | lwt_live_update | 500 ops/sec | ✅ Full |

### OpenSearch Workloads
| Workload | Description | Setup Phases | Run Phase | Default Throughput | Docker Support |
|----------|-------------|--------------|-----------|-------------------|----------------|
| **opensearch-basic** | Basic CRUD operations | pre_cleanup, schema, rampup | search | 2,000 ops/sec | ✅ Full |
| **opensearch-vector** | Vector search operations | pre_cleanup, schema, rampup | search | 1,000 ops/sec | ✅ Full |
| **opensearch-bulk** | Bulk operations | pre_cleanup, schema, bulk_load | verify | 1,500 ops/sec | ✅ Full |

### Presto/Trino Workloads
| Workload | Description | Setup Phases | Run Phase | Default Throughput | Docker Support |
|----------|-------------|--------------|-----------|-------------------|----------------|
| **presto-analytics** | TPC-H inspired analytics | drop, schema, rampup | analytics | 100 ops/sec | ✅ Full |
| **presto-ecommerce** | E-commerce transactions | drop, schema, rampup | transactions | 200 ops/sec | ✅ Full |

## ⚙️ Configuration

### Environment Variables
All configuration is managed through the `.env` file. Key parameters:

```bash
# Database endpoints
CASSANDRA_HOST=cassandra
OPENSEARCH_HOST=opensearch
PRESTO_HOST=trino

# Throughput settings
SAI_THROUGHPUT=1000
LWT_THROUGHPUT=500
OPENSEARCH_BASIC_THROUGHPUT=2000
# ... and more

# Setup timeout (user preference: 10 minutes)
SETUP_TIMEOUT=600
```

### User Preferences Applied
- **Cassandra localdc**: Hardcoded to `datacenter1` to resolve datacenter specification errors
- **SAI ALLOW FILTERING**: All SAI queries include `ALLOW FILTERING` clause
- **Setup timeout**: Set to 10 minutes instead of default 5 minutes
- **Benchmark controls**: Appear as soon as individual workload setup completes

## 🔧 Management Commands

### Infrastructure Management
```bash
./manage.sh start monitoring    # Start monitoring only
./manage.sh start databases     # Start databases only
./manage.sh start all          # Start everything

./manage.sh stop all           # Stop everything
./manage.sh status             # Show service status
./manage.sh cleanup            # Remove all containers and volumes
```

### Workload Management
```bash
./manage.sh setup cassandra-sai       # Setup SAI workload
./manage.sh run opensearch-basic      # Run OpenSearch benchmark
./manage.sh logs grafana -f           # Follow Grafana logs
```

### Available Workload Names
- `cassandra-sai`
- `cassandra-lwt`
- `opensearch-basic`
- `opensearch-vector`
- `opensearch-bulk`
- `presto-analytics`
- `presto-ecommerce`

## 📈 Monitoring and Metrics

### Grafana Dashboards
Access Grafana at http://localhost:3000 with admin/admin:

- **NoSQLBench Overview**: Real-time metrics from all workloads
- **Database Performance**: Database-specific metrics
- **System Resources**: CPU, memory, disk usage

### Metrics Collection
- **NoSQLBench** → VictoriaMetrics (Prometheus format)
- **OpenSearch Benchmark** → Graphite (StatsD format)
- **System metrics** → Node Exporter → VictoriaMetrics

### Results Storage
All benchmark results are stored in `../results/` directory:
- CSV metrics files
- Histogram logs
- Performance statistics

## 🔍 Troubleshooting

### Common Issues

1. **Docker image not found**: Run `docker pull nosqlbench/nosqlbench:5.21.8-preview` to download the image
2. **Port conflicts**: Ensure ports 3000, 8428, 8081, 9042, 9200, 8080, 5432 are available
3. **Memory issues**: Increase Docker memory limit to at least 8GB
4. **Setup timeouts**: Increase `SETUP_TIMEOUT` in `.env` if needed
5. **Network connectivity**: Ensure Docker containers can reach database endpoints

### Health Checks
```bash
./manage.sh status              # Check all services
docker-compose logs cassandra   # Check specific service logs
```

### Reset Everything
```bash
./manage.sh cleanup             # Remove all containers and data
./manage.sh start all           # Fresh start
```

## 📁 Directory Structure

```
docker/
├── manage.sh                           # Main management script
├── .env                               # Environment configuration
├── docker-compose.yml                 # Main compose file
├── docker-compose.monitoring.yml      # Monitoring stack
├── docker-compose.databases.yml       # Database stack
├── docker-compose.nosqlbench-setup.yml # Setup containers
├── docker-compose.nosqlbench-run.yml   # Benchmark containers
├── monitoring/                        # Monitoring configurations
│   ├── grafana/                       # Grafana dashboards and datasources
│   └── graphite/                      # Graphite configuration
├── databases/                         # Database configurations
│   ├── cassandra/                     # Cassandra config files
│   ├── opensearch/                    # OpenSearch config files
│   ├── trino/                         # Trino config and catalogs
│   └── postgres/                      # PostgreSQL init scripts
└── nosqlbench/                        # NoSQLBench scripts
    └── scripts/                       # Helper scripts
```

## 🎯 Next Steps

1. **Start the infrastructure**: `./manage.sh start all`
2. **Run setup phases**: `./manage.sh setup`
3. **Start benchmarks**: `./manage.sh run`
4. **Monitor in Grafana**: http://localhost:3000
5. **Analyze results**: Check `../results/` directory

The infrastructure is designed to be production-ready with proper health checks, monitoring, and user preferences applied throughout.
