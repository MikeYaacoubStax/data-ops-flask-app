# NoSQLBench Demo Flask Application

A comprehensive web-based dashboard for managing and monitoring NoSQLBench workloads across multiple database systems including Cassandra, OpenSearch, and Presto. This application provides a user-friendly interface for setting up infrastructure, configuring databases, running benchmarks, and monitoring performance metrics in real-time.

## 🚀 Features

- **Web-based Dashboard**: Intuitive interface for managing NoSQLBench workloads
- **Multi-Database Support**: Cassandra, OpenSearch, and Presto integration
- **Real-time Monitoring**: Live metrics via Grafana and VictoriaMetrics
- **Complete Docker Infrastructure**: Comprehensive testing environment in `docker/` folder
- **Automated Infrastructure**: Docker-based monitoring and database stack deployment
- **Workload Management**: Setup, start, stop, and monitor benchmark workloads
- **State Persistence**: Application state maintained across restarts
- **WebSocket Updates**: Real-time status updates without page refresh
- **Hybrid Execution**: Flask app + Docker infrastructure + local nb5 command support

## 📋 Prerequisites

### Required Software
- **Python 3.8+** with pip
- **Docker** and Docker Compose
- **NoSQLBench (nb5)** - **CRITICAL: Custom build required (see below)**
- **Database Systems** (at least one):
  - Apache Cassandra
  - OpenSearch/Elasticsearch
  - PrestoDB/Trino

### ✅ **NoSQLBench Docker Image with Full Driver Support**

**The application now uses `nosqlbench/nosqlbench:5.21.8-preview` which includes OpenSearch and Presto/Trino drivers.**

**What's Included:**
- All standard NoSQLBench drivers (CQL, HTTP, etc.)
- OpenSearch driver for search workloads
- JDBC driver for Presto/Trino workloads
- No custom builds or local installations required

**Workload Support Status:**
- ✅ **Cassandra workloads**: Fully supported
- ✅ **OpenSearch workloads**: Fully supported
- ✅ **Presto/Trino workloads**: Fully supported

**Docker Integration:**
- Flask app uses Docker containers automatically
- Docker Compose infrastructure uses the preview image
- No local nb5 command installation needed

### System Requirements
- 4GB+ RAM recommended
- 10GB+ free disk space
- Network access to target databases

## 🛠️ Installation

### 1. Clone and Setup
```bash
git clone <repository-url>
cd data-ops-flask-app

# Create virtual environment (recommended)
python -m venv data-ops-venv
source data-ops-venv/bin/activate  # On Windows: data-ops-venv\Scripts\activate

# Install dependencies
cd app
pip install -r requirements.txt
```

### 2. Verify Docker Installation

**✅ No NoSQLBench installation required - uses Docker containers!**

```bash
# Verify Docker is working
docker --version
docker-compose --version

# Test NoSQLBench preview image
docker run --rm nosqlbench/nosqlbench:5.21.8-preview nb5 --version
docker run --rm nosqlbench/nosqlbench:5.21.8-preview nb5 --list-drivers
```

### 3. Verify Installation
```bash
# Check all prerequisites and Docker setup
cd app
python run_demo.py
```

## 🚀 Quick Start

### Option 1: Using the Launcher (Recommended)
```bash
cd app
python run_demo.py
```

### Option 2: Direct Flask Run
```bash
cd app
python app.py
```

The dashboard will be available at: **http://localhost:5000**

## 🐳 Docker Infrastructure Quick Reference

The `docker/` folder contains a complete NoSQLBench testing infrastructure. See `docker/README.md` for full documentation.

### Quick Commands
```bash
cd docker

# Start everything
./manage.sh start all

# Validate setup
./validate.sh

# Run workloads with local nb5 (recommended for OpenSearch/Presto)
./run-local-nb5.sh check
./run-local-nb5.sh setup-opensearch-basic
./run-local-nb5.sh run-presto-analytics
```

### Access Points
- **Grafana**: http://localhost:3000 (admin/admin)
- **VictoriaMetrics**: http://localhost:8428
- **Cassandra**: localhost:9042
- **OpenSearch**: http://localhost:9200
- **Trino**: http://localhost:8080

## 📖 Usage Guide

### Step 1: Infrastructure Setup
1. **Start Monitoring Stack**
   - Click "Start Infrastructure" to deploy Grafana and VictoriaMetrics containers
   - Wait for containers to be ready (green status indicators)
   - Grafana will be available at http://localhost:3001 (admin/admin)

### Step 2: Database Configuration
1. **Configure Database Endpoints**
   - Enter connection details for your databases:
     - **Cassandra**: Host and port (default: 127.0.0.1:9042)
     - **OpenSearch**: Host and port (default: 127.0.0.1:9200)
     - **Presto**: Host, port, and user (default: 127.0.0.1:8080, testuser)
   - Click "Save Configuration"

### Step 3: Workload Setup
1. **Select Workloads**
   - Choose workloads based on your configured databases
   - Available workloads:
     - `cassandra_sai`: SAI (Storage Attached Index) operations
     - `cassandra_lwt`: Lightweight Transactions
     - `opensearch_basic`: Basic CRUD operations
     - `opensearch_vector`: Vector search operations
     - `opensearch_bulk`: Bulk operations
     - `presto_analytics`: TPC-H inspired analytics
     - `presto_ecommerce`: E-commerce transactions

2. **Run Setup**
   - Click "Run Setup" to initialize schemas and load initial data
   - Monitor progress in real-time
   - Setup includes schema creation, data loading, and index creation

### Step 4: Run Benchmarks
1. **Start Benchmarks**
   - After setup completion, benchmark controls become available
   - Set cycle rate (operations per second)
   - Click "Start" for desired workloads

2. **Monitor Performance**
   - View real-time metrics in the dashboard
   - Access detailed Grafana dashboards
   - Monitor running time, throughput, and errors

3. **Manage Running Benchmarks**
   - Adjust cycle rates dynamically
   - Stop individual benchmarks
   - View runtime statistics

## 🔧 Configuration

### Environment Variables
```bash
# Flask configuration
export FLASK_DEBUG=True
export SECRET_KEY=your-secret-key

# Infrastructure ports
export GRAFANA_PORT=3001
export VICTORIAMETRICS_PORT=8428
```

### Database Configuration
The application supports dynamic database configuration through the web interface. Configuration is persisted in `app_state.json`.

### Workload Configuration
Workload definitions are in `config.py`. Each workload includes:
- **File**: YAML workload definition
- **Setup Phases**: Required initialization steps
- **Run Phase**: Long-running benchmark phase
- **Driver**: Database driver (cql, opensearch, jdbc)

## 📊 Monitoring and Metrics

### Built-in Dashboard
- Real-time benchmark status
- Running time and cycle rates
- Error counts and success rates
- Infrastructure health

### Grafana Integration
- Detailed performance metrics
- Historical data visualization
- Custom dashboards for each database type
- Alerting capabilities

### Metrics Collection
- **VictoriaMetrics**: Time-series database for metrics storage
- **Prometheus Format**: Standard metrics format
- **Real-time Updates**: 2-second refresh intervals



## 🐳 Docker Integration

### Comprehensive Docker Infrastructure
The `docker/` folder contains a complete NoSQLBench testing infrastructure:

```bash
cd docker

# Start complete infrastructure (databases + monitoring)
./manage.sh start all

# Or start components separately
./manage.sh start monitoring  # Grafana, VictoriaMetrics, Graphite
./manage.sh start databases   # Cassandra, OpenSearch, Trino, PostgreSQL
```

**Available Services:**
- **Databases**: Cassandra (9042), OpenSearch (9200), Trino (8080), PostgreSQL (5432)
- **Monitoring**: Grafana (3000), VictoriaMetrics (8428), Graphite (8081)

### NoSQLBench Workload Execution

**Option A: Flask App (All workloads)**
```bash
cd app
python app.py  # Uses local nb5 command
```

**Option B: Direct Docker Management**
```bash
cd docker
./manage.sh setup cassandra-sai    # Cassandra works with Docker
./run-local-nb5.sh setup-opensearch-basic  # OpenSearch requires local nb5
./run-local-nb5.sh setup-presto-analytics  # Presto requires local nb5
```

## 🔍 Troubleshooting

### Common Issues

**Docker or NoSQLBench issues**
```bash
# Verify Docker is working
docker ps
docker run --rm nosqlbench:5.21.8-preview nb5 --version

# Check if preview image is available
docker pull nosqlbench:5.21.8-preview

# Verify drivers are available
docker run --rm nosqlbench:5.21.8-preview nb5 --list-drivers | grep -E "opensearch|jdbc"
```

**Workload failures**
- Ensure Docker daemon is running
- Check that the `nosqlbench:5.21.8-preview` image is available
- Verify database endpoints are accessible from Docker containers

**Docker connection errors**
```bash
# Check Docker daemon
docker ps
docker info
```

**Database connection failures**
- Verify database endpoints are accessible
- Check firewall settings
- Ensure databases are running and accepting connections

**Port conflicts**
- Default ports: 5000 (Flask), 3001 (Grafana), 8428 (VictoriaMetrics)
- Modify ports in `config.py` if needed

### Logs and Debugging
- Application logs: Console output
- NoSQLBench logs: `logs/` directory
- Docker logs: `docker logs <container-name>`

### State Recovery
If the application state becomes corrupted:
```bash
# Remove state file to reset (from project root)
rm app_state.json
```


### Environment-Specific Settings

**Development Environment**
```bash
export FLASK_DEBUG=True
export FLASK_ENV=development
```

**Production Environment**
```bash
export FLASK_DEBUG=False
export SECRET_KEY=secure-random-key
export FLASK_ENV=production
```

### Database-Specific Configuration

**Cassandra Settings**
- Uses `localdc=datacenter1` by default
- Supports keyspace auto-creation
- SAI workloads include `ALLOW FILTERING` clauses

**OpenSearch Settings**
- Supports both OpenSearch and Elasticsearch
- Vector search capabilities
- Bulk operation optimization

**Presto/Trino Settings**
- Memory catalog by default
- Supports multiple catalogs
- TPC-H compatible schemas

## 📈 Performance Tuning

### Benchmark Optimization
- **Cycle Rates**: Start with low rates (10-50 ops/sec) and increase gradually
- **Thread Count**: Use `threads=auto` for optimal performance
- **Batch Sizes**: Adjust based on database capabilities

### System Resources
- **Memory**: Allocate sufficient heap for NoSQLBench processes
- **CPU**: Monitor CPU usage during high-throughput tests
- **Network**: Ensure low latency to database endpoints

### Monitoring Best Practices
- **Baseline Metrics**: Establish baseline performance before testing
- **Resource Monitoring**: Monitor database server resources
- **Error Tracking**: Set up alerts for error rate thresholds

## 🔐 Security Considerations

### Network Security
- **Firewall Rules**: Restrict access to database ports
- **VPN Access**: Use VPN for remote database connections
- **SSL/TLS**: Enable encryption for production databases

### Application Security
- **Secret Management**: Use environment variables for sensitive data
- **Access Control**: Implement authentication for production deployments
- **Input Validation**: All user inputs are validated and sanitized

### Database Security
- **Authentication**: Configure database authentication
- **Authorization**: Use least-privilege access principles
- **Audit Logging**: Enable database audit logs

## 🧪 Testing

### Unit Tests
```bash
# Run unit tests (if available)
python -m pytest tests/
```

### Integration Tests
```bash
# Test database connectivity
python -c "from services.benchmark_manager import BenchmarkManager; print('OK')"
```

### Load Testing
- Start with small workloads to verify setup
- Gradually increase load to find performance limits
- Monitor system resources during tests

## 📁 Project Structure

This project is organized into three main deployment options:

```
data-ops-flask-app/
├── app/                          # 🌐 Flask Web Application
│   ├── app.py                    # Main Flask application
│   ├── config.py                 # Configuration and workload definitions
│   ├── run_demo.py              # Application launcher
│   ├── requirements.txt         # Python dependencies
│   ├── services/                # Core service modules
│   ├── templates/               # HTML templates
│   ├── static/                  # Frontend assets
│   └── README.md                # App-specific documentation
├── docker/                      # 🐳 Docker Infrastructure
│   ├── docker-compose.yml       # Main compose file
│   ├── manage.sh                # Management script
│   ├── monitoring/              # Grafana dashboards
│   ├── databases/               # Database configurations
│   └── README.md                # Docker-specific documentation
├── helm/                        # ☸️ Kubernetes Helm Chart (planned)
├── demo_workloads/              # 📊 Shared NoSQLBench workload definitions
├── logs/                        # 📝 Shared execution logs
├── results/                     # 📈 Shared benchmark results
├── app_state.json              # 💾 Application state persistence
└── README.md                    # Main project documentation
```

### Deployment Options

1. **Flask App** (`app/`): Interactive web interface for workload management
2. **Docker Infrastructure** (`docker/`): Complete containerized testing environment
3. **Helm Chart** (`helm/`): Kubernetes-native deployment (planned)

Each option can be used independently or together based on your deployment needs.

## 📚 Additional Resources

- [NoSQLBench Documentation](https://docs.nosqlbench.io/)
- [Grafana Documentation](https://grafana.com/docs/)
- [VictoriaMetrics Documentation](https://docs.victoriametrics.com/)
- [Flask Documentation](https://flask.palletsprojects.com/)

## 🏷️ Version History

- **v1.0.0**: Initial release with multi-database support
- **v1.1.0**: Added real-time monitoring and WebSocket updates
- **v1.2.0**: Enhanced state management and graceful shutdown
