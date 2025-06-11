#!/bin/bash

# NoSQLBench Docker Infrastructure Management Script
# This script provides a unified interface to manage the entire NoSQLBench testing infrastructure

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

# Function to check if Docker and Docker Compose are available
check_dependencies() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed or not in PATH"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed or not in PATH"
        exit 1
    fi
}

# Function to create necessary directories
create_directories() {
    print_status "Creating necessary directories..."
    mkdir -p ../results
    mkdir -p monitoring/grafana/dashboards/system
    print_status "Directories created successfully"
}

# Function to start monitoring stack
start_monitoring() {
    print_header "Starting Monitoring Stack"
    docker-compose -f docker-compose.monitoring.yml up -d
    print_status "Monitoring stack started. Access Grafana at http://localhost:3001 (admin/admin)"
}

# Function to start database stack
start_databases() {
    print_header "Starting Database Stack"
    docker-compose --profile databases up -d
    print_status "Database stack started"
    print_status "Cassandra CQL: localhost:9042"
    print_status "OpenSearch HTTP: localhost:9200"
    print_status "Trino HTTP: localhost:8080"
}

# Function to start everything
start_all() {
    print_header "Starting Complete Infrastructure"
    create_directories
    docker-compose --profile all up -d
    print_status "Complete infrastructure started"
    print_status "Services available:"
    print_status "  - Grafana: http://localhost:3000 (admin/admin)"
    print_status "  - VictoriaMetrics: http://localhost:8428"
    print_status "  - Graphite: http://localhost:8081"
    print_status "  - Cassandra: localhost:9042"
    print_status "  - OpenSearch: http://localhost:9200"
    print_status "  - Trino: http://localhost:8080"
}

# Function to run setup phases
run_setup() {
    local workload="$1"
    print_header "Running Setup Phase"
    
    if [ -z "$workload" ]; then
        print_status "Running setup for all workloads..."
        docker-compose -f docker-compose.nosqlbench-setup.yml --profile setup up
    else
        print_status "Running setup for workload: $workload"
        docker-compose -f docker-compose.nosqlbench-setup.yml up "nb-setup-$workload"
    fi
}

# Function to run benchmark phases
run_benchmarks() {
    local workload="$1"
    print_header "Running Benchmark Phase"
    
    if [ -z "$workload" ]; then
        print_status "Running benchmarks for all workloads..."
        docker-compose -f docker-compose.nosqlbench-run.yml --profile run up -d
    else
        print_status "Running benchmark for workload: $workload"
        docker-compose -f docker-compose.nosqlbench-run.yml up -d "nb-run-$workload"
    fi
}

# Function to stop services
stop_services() {
    local service_type="$1"
    print_header "Stopping Services"
    
    case "$service_type" in
        "monitoring")
            docker-compose --profile monitoring down
            ;;
        "databases")
            docker-compose --profile databases down
            ;;
        "setup")
            docker-compose -f docker-compose.nosqlbench-setup.yml --profile setup down
            ;;
        "run")
            docker-compose -f docker-compose.nosqlbench-run.yml --profile run down
            ;;
        "all"|"")
            print_status "Stopping NoSQLBench run containers..."
            docker-compose -f docker-compose.nosqlbench-run.yml --profile run down || print_warning "No run containers to stop"
            print_status "Stopping NoSQLBench setup containers..."
            docker-compose -f docker-compose.nosqlbench-setup.yml --profile setup down || print_warning "No setup containers to stop"
            print_status "Stopping infrastructure services..."
            docker-compose --profile all down
            print_status "Stopping any remaining NoSQLBench containers..."
            docker stop $(docker ps -q --filter "name=nb-") 2>/dev/null || print_warning "No additional NoSQLBench containers found"
            ;;
        *)
            print_error "Unknown service type: $service_type"
            exit 1
            ;;
    esac
    print_status "Services stopped"
}

# Function to show status
show_status() {
    print_header "Service Status"
    docker-compose ps
    echo
    print_header "Running NoSQLBench Containers"
    docker ps --filter "name=nb-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
}

# Function to show logs
show_logs() {
    local service="$1"
    local follow="$2"
    
    if [ -z "$service" ]; then
        print_error "Please specify a service name"
        exit 1
    fi
    
    if [ "$follow" = "-f" ] || [ "$follow" = "--follow" ]; then
        docker-compose logs -f "$service"
    else
        docker-compose logs "$service"
    fi
}

# Function to clean up everything
cleanup() {
    print_header "Cleaning Up Infrastructure"
    print_warning "This will remove all containers, volumes, and networks"
    read -p "Are you sure? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        stop_services "all"
        print_status "Removing volumes and networks..."
        docker-compose -f docker-compose.nosqlbench-run.yml --profile run down -v 2>/dev/null || true
        docker-compose -f docker-compose.nosqlbench-setup.yml --profile setup down -v 2>/dev/null || true
        docker-compose --profile all down -v
        print_status "Removing any remaining NoSQLBench containers..."
        docker rm -f $(docker ps -aq --filter "name=nb-") 2>/dev/null || true
        print_status "Pruning Docker system..."
        docker system prune -f
        print_status "Cleanup completed"
    else
        print_status "Cleanup cancelled"
    fi
}

# Function to show help
show_help() {
    cat << EOF
NoSQLBench Docker Infrastructure Management

Usage: $0 <command> [options]

Commands:
  start monitoring              Start monitoring stack (Grafana, VictoriaMetrics, Graphite)
  start databases              Start database stack (Cassandra, OpenSearch, Trino)
  start all                    Start complete infrastructure
  
  setup [workload]             Run setup phases for workloads
                              Available workloads: cassandra-sai, cassandra-lwt, 
                              opensearch-basic, opensearch-vector, opensearch-bulk,
                              presto-analytics, presto-ecommerce
  
  run [workload]               Run benchmark phases for workloads
  
  stop [monitoring|databases|setup|run|all]  Stop specified services
  
  status                       Show status of all services
  logs <service> [-f]          Show logs for a service (use -f to follow)
  cleanup                      Remove all containers, volumes, and networks
  
  help                         Show this help message

Examples:
  $0 start all                 # Start complete infrastructure
  $0 setup cassandra-sai       # Run setup for SAI workload only
  $0 run opensearch-basic      # Run OpenSearch basic benchmark
  $0 logs grafana -f           # Follow Grafana logs
  $0 stop all                  # Stop everything

Environment Variables:
  See .env file for configuration options including throughput settings,
  database endpoints, and other parameters.

EOF
}

# Main script logic
main() {
    check_dependencies
    
    case "${1:-help}" in
        "start")
            case "${2:-all}" in
                "monitoring") start_monitoring ;;
                "databases") start_databases ;;
                "all") start_all ;;
                *) print_error "Unknown start option: $2"; show_help; exit 1 ;;
            esac
            ;;
        "setup")
            run_setup "$2"
            ;;
        "run")
            run_benchmarks "$2"
            ;;
        "stop")
            stop_services "$2"
            ;;
        "status")
            show_status
            ;;
        "logs")
            show_logs "$2" "$3"
            ;;
        "cleanup")
            cleanup
            ;;
        "help"|"-h"|"--help")
            show_help
            ;;
        *)
            print_error "Unknown command: $1"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
