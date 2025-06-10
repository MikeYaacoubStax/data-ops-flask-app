#!/bin/bash

# NoSQLBench Local nb5 Command Runner
# This script provides examples of running NoSQLBench workloads using the local nb5 command
# instead of Docker containers (required for OpenSearch and Presto/Trino workloads)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKLOADS_DIR="$(cd "$SCRIPT_DIR/../demo_workloads" && pwd)"
RESULTS_DIR="$(cd "$SCRIPT_DIR/../results" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Check if NoSQLBench Docker image is available
check_nb5() {
    if ! docker image inspect nosqlbench/nosqlbench:5.21.8-preview &> /dev/null; then
        print_error "NoSQLBench preview image not found!"
        echo
        print_error "Please pull the required Docker image:"
        echo "docker pull nosqlbench/nosqlbench:5.21.8-preview"
        echo
        exit 1
    fi

    print_status "NoSQLBench preview image found: nosqlbench/nosqlbench:5.21.8-preview"

    # Check if required drivers are available
    if docker run --rm nosqlbench/nosqlbench:5.21.8-preview nb5 --list-drivers | grep -q "opensearch\|jdbc"; then
        print_status "OpenSearch and JDBC drivers are available"
    else
        print_warning "OpenSearch or JDBC drivers may not be available"
        print_warning "Verify the Docker image version"
    fi

    # Check if local nb5 is also available (optional)
    if command -v nb5 &> /dev/null; then
        print_status "Local nb5 command also found: $(which nb5)"
        print_status "This script will use Docker containers for consistency"
    fi
}

# Load environment variables
load_env() {
    if [ -f "$SCRIPT_DIR/.env" ]; then
        source "$SCRIPT_DIR/.env"
        print_status "Environment variables loaded from .env"
    else
        print_warning ".env file not found, using defaults"
        # Set defaults
        CASSANDRA_HOST=${CASSANDRA_HOST:-localhost}
        CASSANDRA_PORT=${CASSANDRA_PORT:-9042}
        CASSANDRA_LOCALDC=${CASSANDRA_LOCALDC:-datacenter1}
        OPENSEARCH_HOST=${OPENSEARCH_HOST:-localhost}
        OPENSEARCH_PORT=${OPENSEARCH_PORT:-9200}
        PRESTO_HOST=${PRESTO_HOST:-localhost}
        PRESTO_PORT=${PRESTO_PORT:-8080}
        PRESTO_USER=${PRESTO_USER:-testuser}
    fi
}

# Function to run NoSQLBench via Docker
run_nb5_docker() {
    local workload_file="$1"
    shift
    local args="$@"

    docker run --rm \
        --network host \
        -v "$WORKLOADS_DIR:/workloads" \
        -v "$RESULTS_DIR:/results" \
        nosqlbench/nosqlbench:5.21.8-preview \
        nb5 "/workloads/$(basename "$workload_file")" $args
}

# Function to run Cassandra SAI setup
run_cassandra_sai_setup() {
    print_header "Running Cassandra SAI Setup"

    print_status "Creating schema..."
    run_nb5_docker "$WORKLOADS_DIR/sai_longrun.yaml" setup.schema \
        driver=cql \
        host="$CASSANDRA_HOST" \
        port="$CASSANDRA_PORT" \
        localdc="$CASSANDRA_LOCALDC"

    print_status "Running rampup..."
    run_nb5_docker "$WORKLOADS_DIR/sai_longrun.yaml" setup.rampup \
        driver=cql \
        host="$CASSANDRA_HOST" \
        port="$CASSANDRA_PORT" \
        localdc="$CASSANDRA_LOCALDC" \
        threads=auto \
        cycles=10000

    print_status "SAI setup completed"
}

# Function to run Cassandra SAI benchmark
run_cassandra_sai_benchmark() {
    print_header "Running Cassandra SAI Benchmark"

    run_nb5_docker "$WORKLOADS_DIR/sai_longrun.yaml" sai_reads_test.sai_reads \
        driver=cql \
        host="$CASSANDRA_HOST" \
        port="$CASSANDRA_PORT" \
        localdc="$CASSANDRA_LOCALDC" \
        threads=auto \
        cycles="${SAI_CYCLES:-3000000000}" \
        cyclerate="${SAI_THROUGHPUT:-1000}" \
        ts_window=10 \
        prior_inserts=10000 \
        price_window=10 \
        --report-csv-to "/results/sai-metrics.csv" \
        --report-interval 10s \
        --progress console:1s
}

# Function to run OpenSearch Basic setup
run_opensearch_basic_setup() {
    print_header "Running OpenSearch Basic Setup"

    print_status "Cleaning up..."
    run_nb5_docker "$WORKLOADS_DIR/opensearch_basic_longrun.yaml" default.pre_cleanup \
        driver=opensearch \
        host="$OPENSEARCH_HOST" \
        port="$OPENSEARCH_PORT"

    print_status "Creating schema..."
    run_nb5_docker "$WORKLOADS_DIR/opensearch_basic_longrun.yaml" default.schema \
        driver=opensearch \
        host="$OPENSEARCH_HOST" \
        port="$OPENSEARCH_PORT"

    print_status "Running rampup..."
    run_nb5_docker "$WORKLOADS_DIR/opensearch_basic_longrun.yaml" default.rampup \
        driver=opensearch \
        host="$OPENSEARCH_HOST" \
        port="$OPENSEARCH_PORT" \
        threads=10 \
        cycles=1000

    print_status "OpenSearch Basic setup completed"
}

# Function to run OpenSearch Basic benchmark
run_opensearch_basic_benchmark() {
    print_header "Running OpenSearch Basic Benchmark"

    run_nb5_docker "$WORKLOADS_DIR/opensearch_basic_longrun.yaml" default.search \
        driver=opensearch \
        host="$OPENSEARCH_HOST" \
        port="$OPENSEARCH_PORT" \
        threads="${OPENSEARCH_BASIC_THREADS:-5}" \
        cycles="${OPENSEARCH_BASIC_CYCLES:-3000000000}" \
        cyclerate="${OPENSEARCH_BASIC_THROUGHPUT:-2000}" \
        --report-csv-to "/results/opensearch-basic-metrics.csv" \
        --report-interval 10s \
        --progress console:1s
}

# Function to run Presto Analytics setup
run_presto_analytics_setup() {
    print_header "Running Presto Analytics Setup"

    local dburl="jdbc:presto://$PRESTO_HOST:$PRESTO_PORT/memory?user=$PRESTO_USER"

    print_status "Dropping tables..."
    run_nb5_docker "$WORKLOADS_DIR/jdbc_analytics_longrun.yaml" default.drop \
        dburl="$dburl" \
        use_hikaricp=true

    print_status "Creating schema..."
    run_nb5_docker "$WORKLOADS_DIR/jdbc_analytics_longrun.yaml" default.schema \
        dburl="$dburl" \
        use_hikaricp=true

    print_status "Running rampup..."
    run_nb5_docker "$WORKLOADS_DIR/jdbc_analytics_longrun.yaml" default.rampup \
        dburl="$dburl" \
        use_hikaricp=true \
        threads=10 \
        cycles=5000

    print_status "Presto Analytics setup completed"
}

# Function to run Presto Analytics benchmark
run_presto_analytics_benchmark() {
    print_header "Running Presto Analytics Benchmark"

    local dburl="jdbc:presto://$PRESTO_HOST:$PRESTO_PORT/memory?user=$PRESTO_USER"

    run_nb5_docker "$WORKLOADS_DIR/jdbc_analytics_longrun.yaml" default.analytics \
        dburl="$dburl" \
        use_hikaricp=true \
        threads="${PRESTO_ANALYTICS_THREADS:-5}" \
        cycles="${PRESTO_ANALYTICS_CYCLES:-3000000000}" \
        cyclerate="${PRESTO_ANALYTICS_THROUGHPUT:-100}" \
        --report-csv-to "/results/presto-analytics-metrics.csv" \
        --report-interval 10s \
        --progress console:1s
}

# Function to show available commands
show_help() {
    cat << EOF
NoSQLBench Docker Command Runner

This script provides examples of running NoSQLBench workloads using Docker containers.
Uses the nosqlbench/nosqlbench:5.21.8-preview image with full driver support.

Usage: $0 <command>

Setup Commands:
  setup-cassandra-sai       Setup Cassandra SAI workload
  setup-opensearch-basic    Setup OpenSearch Basic workload
  setup-presto-analytics    Setup Presto Analytics workload

Benchmark Commands:
  run-cassandra-sai         Run Cassandra SAI benchmark
  run-opensearch-basic      Run OpenSearch Basic benchmark
  run-presto-analytics      Run Presto Analytics benchmark

Utility Commands:
  check                     Check Docker image and drivers
  help                      Show this help message

Prerequisites:
  1. Docker installed and running
  2. NoSQLBench preview image: docker pull nosqlbench/nosqlbench:5.21.8-preview
  3. Start databases: ./manage.sh start databases

Examples:
  $0 check                      # Verify nb5 installation
  $0 setup-cassandra-sai        # Setup SAI workload
  $0 run-opensearch-basic       # Run OpenSearch benchmark

Environment Variables (from .env):
  CASSANDRA_HOST=$CASSANDRA_HOST
  OPENSEARCH_HOST=$OPENSEARCH_HOST  
  PRESTO_HOST=$PRESTO_HOST

EOF
}

# Main script logic
main() {
    case "${1:-help}" in
        "check")
            check_nb5
            ;;
        "setup-cassandra-sai")
            check_nb5
            load_env
            run_cassandra_sai_setup
            ;;
        "setup-opensearch-basic")
            check_nb5
            load_env
            run_opensearch_basic_setup
            ;;
        "setup-presto-analytics")
            check_nb5
            load_env
            run_presto_analytics_setup
            ;;
        "run-cassandra-sai")
            check_nb5
            load_env
            run_cassandra_sai_benchmark
            ;;
        "run-opensearch-basic")
            check_nb5
            load_env
            run_opensearch_basic_benchmark
            ;;
        "run-presto-analytics")
            check_nb5
            load_env
            run_presto_analytics_benchmark
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
