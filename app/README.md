# NoSQLBench Flask Application

This is the Flask web application component of the NoSQLBench Demo project. It provides a web-based interface for managing NoSQLBench workloads and benchmarks.

## Features

- **Web Dashboard**: Interactive UI for managing benchmarks
- **Real-time Updates**: WebSocket-based status updates
- **Database Configuration**: Dynamic database endpoint configuration
- **Workload Management**: Setup and execution of NoSQLBench workloads
- **Benchmark Control**: Start, stop, and adjust throughput of running benchmarks
- **Progress Tracking**: Real-time monitoring of setup and benchmark phases

## Quick Start

### Prerequisites

1. **Python 3.8+**
2. **Docker** (for NoSQLBench execution)
3. **NoSQLBench** (optional - can use Docker mode)

### Installation

1. **Install dependencies**:
   ```bash
   cd app
   pip install -r requirements.txt
   ```

2. **Run the application**:
   ```bash
   python run_demo.py
   ```

3. **Access the dashboard**:
   Open http://localhost:5000 in your browser

## Configuration

### Environment Variables

```bash
# Flask configuration
export FLASK_DEBUG=True
export SECRET_KEY=your-secret-key

# Infrastructure ports (if using local monitoring)
export GRAFANA_PORT=3001
export VICTORIAMETRICS_PORT=8428
```

### Database Configuration

Configure database endpoints through the web interface. Configuration is persisted in `../app_state.json`.

Supported databases:
- **Cassandra**: CQL driver
- **OpenSearch**: OpenSearch driver  
- **Presto/Trino**: JDBC driver

## Workloads

The application supports the following workloads:

### Cassandra Workloads
- **SAI (Secondary Index)**: Search and analytics workload
- **LWT (Lightweight Transactions)**: Consistency-focused workload

### OpenSearch Workloads
- **Basic Search**: Standard search operations
- **Vector Search**: Vector similarity search
- **Bulk Operations**: Bulk indexing and verification

### Presto Workloads
- **Analytics**: OLAP-style analytical queries
- **E-commerce**: Transactional workload simulation

## Architecture

### Core Components

- **app.py**: Main Flask application with routes and WebSocket handlers
- **config.py**: Application configuration and workload definitions
- **run_demo.py**: Application launcher with prerequisite checks

### Services

- **benchmark_manager.py**: NoSQLBench process management
- **docker_manager.py**: Docker container management
- **state_manager.py**: Application state persistence

### Frontend

- **templates/**: HTML templates (Jinja2)
- **static/**: CSS, JavaScript, and assets

## Usage

### 1. Configure Databases

1. Access the web dashboard
2. Navigate to database configuration
3. Enter database endpoints (host, port, credentials)
4. Save configuration

### 2. Run Setup

1. Select workloads to set up
2. Click "Run Setup" 
3. Monitor progress in real-time
4. Setup includes: schema creation, data loading, ramp-up

### 3. Start Benchmarks

1. After setup completion, benchmark controls become available
2. Start benchmarks with desired throughput (cycle rate)
3. Monitor real-time metrics
4. Adjust throughput dynamically

### 4. Monitor Results

- **Real-time Dashboard**: Live status and metrics
- **Logs**: Detailed execution logs in `../logs/`
- **Results**: Benchmark results in `../results/`
- **External Monitoring**: VictoriaMetrics + Grafana integration

## Docker Integration

The application can run NoSQLBench in two modes:

### Docker Mode (Default)
- Uses `nosqlbench/nosqlbench:5.21.8-preview` image
- Automatic container management
- Isolated execution environment

### Local Mode
- Requires `nb5` command in PATH
- Direct process execution
- Faster startup, less isolation

Configure in `config.py`:
```python
self.benchmark.use_docker = True  # or False for local mode
```

## API Endpoints

### Status
- `GET /api/status` - Application status
- `GET /api/infrastructure/status` - Infrastructure status

### Configuration  
- `GET /api/databases/config` - Get database configuration
- `POST /api/databases/config` - Update database configuration

### Setup
- `GET /api/setup/status` - Setup status for all workloads
- `POST /api/setup/run` - Run setup for selected workloads

### Benchmarks
- `GET /api/benchmarks/running` - Get running benchmarks
- `POST /api/benchmarks/start` - Start a benchmark
- `POST /api/benchmarks/stop` - Stop a benchmark
- `POST /api/benchmarks/update-throughput` - Update benchmark throughput

### WebSocket Events
- `status_update` - Real-time status updates
- `benchmark_update` - Benchmark status changes
- `setup_progress` - Setup phase progress

## Development

### Project Structure
```
app/
├── app.py                    # Main Flask application
├── config.py                # Configuration and workload definitions
├── run_demo.py              # Application launcher
├── requirements.txt         # Python dependencies
├── services/                # Core service modules
│   ├── benchmark_manager.py # NoSQLBench management
│   ├── docker_manager.py    # Docker integration
│   └── state_manager.py     # State persistence
├── templates/               # HTML templates
│   └── index.html          # Main dashboard
└── static/                 # Frontend assets
    ├── css/                # Stylesheets
    └── js/                 # JavaScript
```

### Adding New Workloads

1. **Add workload YAML** to `../demo_workloads/`
2. **Update config.py** with workload definition:
   ```python
   'new_workload': {
       'file': 'new_workload.yaml',
       'setup_phases': ['phase1', 'phase2'],
       'run_phase': 'main_phase',
       'driver': 'cql|opensearch|jdbc'
   }
   ```
3. **Test** setup and execution

### Debugging

- **Logs**: Check `../logs/` for detailed execution logs
- **State**: Inspect `../app_state.json` for persisted state
- **Flask Debug**: Set `FLASK_DEBUG=True` for detailed error messages
- **WebSocket**: Use browser dev tools to monitor WebSocket messages

## Integration

This Flask application is part of a larger project structure:

- **../docker/**: Complete Docker infrastructure
- **../helm/**: Kubernetes Helm chart (planned)
- **../demo_workloads/**: Shared workload definitions
- **../logs/**: Shared logs directory
- **../results/**: Shared results directory

Each component can be used independently or together for different deployment scenarios.
