#!/bin/bash

# NoSQLBench Docker Infrastructure Validation Script
# This script validates that the infrastructure is working correctly

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_header() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

# Function to check if a service is responding
check_service() {
    local service_name="$1"
    local url="$2"
    local expected_status="${3:-200}"
    
    echo -n "Checking $service_name... "
    
    if curl -s -o /dev/null -w "%{http_code}" "$url" | grep -q "$expected_status"; then
        print_status "$service_name is responding"
        return 0
    else
        print_error "$service_name is not responding"
        return 1
    fi
}

# Function to check if a port is open
check_port() {
    local service_name="$1"
    local host="$2"
    local port="$3"
    
    echo -n "Checking $service_name port... "
    
    if nc -z "$host" "$port" 2>/dev/null; then
        print_status "$service_name port $port is open"
        return 0
    else
        print_error "$service_name port $port is not accessible"
        return 1
    fi
}

# Function to validate Docker Compose files
validate_compose_files() {
    print_header "Validating Docker Compose Files"
    
    local files=(
        "docker-compose.yml"
        "docker-compose.monitoring.yml"
        "docker-compose.databases.yml"
        "docker-compose.nosqlbench-setup.yml"
        "docker-compose.nosqlbench-run.yml"
    )
    
    for file in "${files[@]}"; do
        if [ -f "$file" ]; then
            if docker-compose -f "$file" config > /dev/null 2>&1; then
                print_status "$file is valid"
            else
                print_error "$file has syntax errors"
                return 1
            fi
        else
            print_error "$file not found"
            return 1
        fi
    done
}

# Function to validate configuration files
validate_config_files() {
    print_header "Validating Configuration Files"
    
    local required_files=(
        ".env"
        "monitoring/grafana/provisioning/datasources/datasources.yml"
        "monitoring/grafana/provisioning/dashboards/dashboards.yml"
        "databases/cassandra/cassandra.yaml"
        "databases/opensearch/opensearch.yml"
        "databases/presto/config.properties"
    )
    
    for file in "${required_files[@]}"; do
        if [ -f "$file" ]; then
            print_status "$file exists"
        else
            print_error "$file not found"
            return 1
        fi
    done
}

# Function to validate workload files
validate_workload_files() {
    print_header "Validating Workload Files"
    
    local workload_files=(
        "../demo_workloads/sai_longrun.yaml"
        "../demo_workloads/lwt_longrun.yaml"
        "../demo_workloads/opensearch_basic_longrun.yaml"
        "../demo_workloads/opensearch_vector_search_longrun.yaml"
        "../demo_workloads/opensearch_bulk_longrun.yaml"
        "../demo_workloads/jdbc_analytics_longrun.yaml"
        "../demo_workloads/jdbc_ecommerce_longrun.yaml"
    )
    
    for file in "${workload_files[@]}"; do
        if [ -f "$file" ]; then
            print_status "$(basename "$file") exists"
        else
            print_error "$(basename "$file") not found"
            return 1
        fi
    done
}

# Function to check running services
check_running_services() {
    print_header "Checking Running Services"
    
    # Check if any services are running
    if docker-compose ps | grep -q "Up"; then
        print_status "Some services are running"
        
        # Check individual services
        check_service "Grafana" "http://localhost:3000/api/health"
        check_service "VictoriaMetrics" "http://localhost:8428/health"
        check_service "Graphite" "http://localhost:8081"
        check_service "OpenSearch" "http://localhost:9200/_cluster/health"
        check_service "Presto" "http://localhost:8080/v1/info"
        
        # Check database ports
        check_port "Cassandra" "localhost" "9042"

    else
        print_warning "No services are currently running"
        print_status "Run './manage.sh start all' to start the infrastructure"
    fi
}

# Function to validate environment variables
validate_environment() {
    print_header "Validating Environment Configuration"
    
    if [ -f ".env" ]; then
        source .env
        
        # Check key variables
        local required_vars=(
            "CASSANDRA_HOST"
            "OPENSEARCH_HOST"
            "PRESTO_HOST"
            "GRAFANA_PORT"
            "VICTORIAMETRICS_PORT"
        )
        
        for var in "${required_vars[@]}"; do
            if [ -n "${!var}" ]; then
                print_status "$var is set to: ${!var}"
            else
                print_error "$var is not set"
                return 1
            fi
        done
    else
        print_error ".env file not found"
        return 1
    fi
}

# Function to check Docker and Docker Compose
check_dependencies() {
    print_header "Checking Dependencies"

    if command -v docker &> /dev/null; then
        print_status "Docker is installed: $(docker --version)"
    else
        print_error "Docker is not installed"
        return 1
    fi

    if command -v docker-compose &> /dev/null; then
        print_status "Docker Compose is installed: $(docker-compose --version)"
    else
        print_error "Docker Compose is not installed"
        return 1
    fi

    # Check for NoSQLBench Docker image with required drivers
    if docker image inspect nosqlbench/nosqlbench:5.21.8-preview &> /dev/null; then
        print_status "NoSQLBench preview image is available"

        # Check if required drivers are available in the Docker image
        if docker run --rm nosqlbench/nosqlbench:5.21.8-preview nb5 --list-drivers 2>/dev/null | grep -q "opensearch\|jdbc"; then
            print_status "OpenSearch and JDBC drivers are available in Docker image"
        else
            print_warning "OpenSearch or JDBC drivers may not be available in Docker image"
        fi
    else
        print_warning "NoSQLBench preview image not found"
        print_warning "Run: docker pull nosqlbench/nosqlbench:5.21.8-preview"
    fi

    # Check for optional local nb5 command
    if command -v nb5 &> /dev/null; then
        print_status "Local nb5 command is also available: $(which nb5)"
    else
        print_status "Local nb5 command not found (not required - using Docker)"
    fi
}

# Function to check disk space
check_disk_space() {
    print_header "Checking Disk Space"
    
    local available_space=$(df . | awk 'NR==2 {print $4}')
    local available_gb=$((available_space / 1024 / 1024))
    
    if [ "$available_gb" -gt 10 ]; then
        print_status "Available disk space: ${available_gb}GB"
    else
        print_warning "Low disk space: ${available_gb}GB (recommend at least 10GB)"
    fi
}

# Function to run a quick smoke test
run_smoke_test() {
    print_header "Running Smoke Test"
    
    print_status "Starting minimal infrastructure for testing..."
    
    # Start monitoring only for quick test
    if docker-compose --profile monitoring up -d > /dev/null 2>&1; then
        print_status "Monitoring stack started"
        
        # Wait a bit for services to start
        sleep 10
        
        # Test Grafana
        if check_service "Grafana" "http://localhost:3000/api/health"; then
            print_status "Grafana smoke test passed"
        fi
        
        # Test VictoriaMetrics
        if check_service "VictoriaMetrics" "http://localhost:8428/health"; then
            print_status "VictoriaMetrics smoke test passed"
        fi
        
        # Clean up
        print_status "Stopping test services..."
        docker-compose --profile monitoring down > /dev/null 2>&1
        print_status "Smoke test completed"
    else
        print_error "Failed to start monitoring stack"
        return 1
    fi
}

# Main validation function
main() {
    print_header "NoSQLBench Docker Infrastructure Validation"
    
    local exit_code=0
    
    # Run all validation checks
    check_dependencies || exit_code=1
    validate_compose_files || exit_code=1
    validate_config_files || exit_code=1
    validate_workload_files || exit_code=1
    validate_environment || exit_code=1
    check_disk_space
    check_running_services
    
    # Run smoke test if requested
    if [ "$1" = "--smoke-test" ] || [ "$1" = "-s" ]; then
        run_smoke_test || exit_code=1
    fi
    
    echo
    if [ $exit_code -eq 0 ]; then
        print_header "Validation Completed Successfully"
        print_status "Infrastructure is ready to use"
        echo
        print_status "Next steps:"
        echo "  1. Start infrastructure: ./manage.sh start all"
        echo "  2. Run setup phases: ./manage.sh setup"
        echo "  3. Start benchmarks: ./manage.sh run"
        echo "  4. Access Grafana: http://localhost:3000"
    else
        print_header "Validation Failed"
        print_error "Please fix the issues above before proceeding"
    fi
    
    exit $exit_code
}

# Show help if requested
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    cat << EOF
NoSQLBench Docker Infrastructure Validation

Usage: $0 [options]

Options:
  --smoke-test, -s    Run a quick smoke test with minimal services
  --help, -h          Show this help message

This script validates:
  - Docker and Docker Compose installation
  - Docker Compose file syntax
  - Configuration file presence
  - Workload file availability
  - Environment variable configuration
  - Running service health (if any)
  - Available disk space

EOF
    exit 0
fi

main "$@"
