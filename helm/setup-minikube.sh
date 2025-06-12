 #!/bin/bash
set -e

# NoSQLBench Kubernetes Demo - Minikube Setup Script
# This script sets up the complete environment for testing on minikube
#
# Features:
# - Fast database connectivity checks (direct socket connections)
# - Real-time UI updates without page refreshes
# - Interactive benchmark controls with progress indicators
# - Automatic workload setup and management

echo "🚀 NoSQLBench Kubernetes Demo - Minikube Setup"
echo "=============================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
IMAGE_NAME="nosqlbench-webapp"
IMAGE_TAG="v1.0.0"
RELEASE_NAME="nosqlbench-demo"
NAMESPACE="default"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check if minikube is installed
    if ! command -v minikube &> /dev/null; then
        print_error "minikube is not installed. Please install minikube first."
        echo "Visit: https://minikube.sigs.k8s.io/docs/start/"
        exit 1
    fi
    
    # Check if kubectl is installed
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl is not installed. Please install kubectl first."
        exit 1
    fi
    
    # Check if helm is installed
    if ! command -v helm &> /dev/null; then
        print_error "helm is not installed. Please install helm first."
        echo "Visit: https://helm.sh/docs/intro/install/"
        exit 1
    fi
    
    # Check if docker is installed
    if ! command -v docker &> /dev/null; then
        print_error "docker is not installed. Please install docker first."
        exit 1
    fi
    
    print_success "All prerequisites are installed"
}

# Start minikube
start_minikube() {
    print_status "Starting minikube..."
    
    # Check if minikube is already running
    if minikube status | grep -q "Running"; then
        print_success "minikube is already running"
    else
        print_status "Starting minikube with sufficient resources..."
        minikube start --cpus=4 --memory=8192 --disk-size=20g
        print_success "minikube started successfully"
    fi
    
    # Enable required addons
    print_status "Enabling minikube addons..."
    minikube addons enable ingress
    minikube addons enable metrics-server
    
    print_success "minikube is ready"
}

# Build Docker image in minikube context
build_image() {
    print_status "Building Docker image in minikube context..."
    
    # Set docker environment to minikube
    eval $(minikube docker-env)
    
    # Build the image
    cd docker
    print_status "Building image: ${IMAGE_NAME}:${IMAGE_TAG}"
    docker build -t "${IMAGE_NAME}:${IMAGE_TAG}" .
    
    # Verify image was built
    if docker images | grep -q "${IMAGE_NAME}"; then
        print_success "Docker image built successfully"
        # Show image details
        docker images | grep "${IMAGE_NAME}" | head -1
    else
        print_error "Failed to build Docker image"
        exit 1
    fi
    
    cd ..
}

# Check VictoriaMetrics connectivity
check_victoriametrics() {
    print_status "Checking VictoriaMetrics connectivity..."
    
    # Test if VictoriaMetrics is accessible from host
    if curl -s http://localhost:8428/api/v1/status/config > /dev/null; then
        print_success "VictoriaMetrics is accessible on localhost:8428"
    else
        print_warning "VictoriaMetrics is not accessible on localhost:8428"
        print_warning "Make sure VictoriaMetrics is running with: docker run -p 8428:8428 victoriametrics/victoria-metrics"
    fi
}

# Deploy with Helm
deploy_helm() {
    print_status "Deploying NoSQLBench Demo with Helm..."
    
    # Check if release already exists
    if helm list | grep -q "${RELEASE_NAME}"; then
        print_status "Release ${RELEASE_NAME} already exists, upgrading..."
        helm upgrade "${RELEASE_NAME}" . -f test-values.yaml
    else
        print_status "Installing new release ${RELEASE_NAME}..."
        helm install "${RELEASE_NAME}" . -f test-values.yaml
    fi
    
    print_success "Helm deployment completed"
}

# Wait for deployment
wait_for_deployment() {
    print_status "Waiting for deployment to be ready..."

    # Wait for deployment to be ready
    kubectl wait --for=condition=available --timeout=300s deployment/${RELEASE_NAME}

    # Verify health endpoints are responding
    print_status "Verifying application health..."
    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if kubectl exec deployment/${RELEASE_NAME} -- curl -f http://localhost:5000/api/health > /dev/null 2>&1; then
            print_success "Application health check passed"
            break
        fi

        if [ $attempt -eq $max_attempts ]; then
            print_warning "Health check timeout, but deployment is running"
            break
        fi

        sleep 2
        ((attempt++))
    done

    print_success "Deployment is ready"
}

# Get access information
get_access_info() {
    print_status "Getting access information..."
    
    # Get service URL
    SERVICE_URL=$(minikube service ${RELEASE_NAME} --url)
    
    print_success "Deployment completed successfully!"
    echo ""
    echo "🌐 Access Information:"
    echo "====================="
    echo "Web Interface: ${SERVICE_URL}"
    echo ""
    echo "📊 Next Steps - Configure Database Endpoints:"
    echo "1. Open the web interface above"
    echo "2. Go to 'Database Configuration' section"
    echo "3. Add your database endpoints (examples below):"
    echo "   • Cassandra: 3.91.36.147:9042"
    echo "   • OpenSearch: 3.91.36.147:9200"
    echo "   • Presto: 3.91.36.147:8080"
    echo "4. Test connectivity and run workloads"
    echo ""
    echo "📈 Metrics Endpoint:"
    echo "VictoriaMetrics: http://host.minikube.internal:8428"
    echo ""
    echo "✨ Features:"
    echo "• Dynamic database configuration through web UI"
    echo "• Fast database connectivity checks (direct socket connections)"
    echo "• Real-time UI updates without page refreshes"
    echo "• Interactive benchmark controls with progress indicators"
    echo "• Automatic workload setup and management"
    echo ""
    echo "🔧 Useful Commands:"
    echo "kubectl get pods                    # View pods"
    echo "kubectl get jobs                    # View jobs"
    echo "kubectl logs -l app.kubernetes.io/name=nosqlbench-demo  # View logs"
    echo "minikube service ${RELEASE_NAME}    # Open web interface"
    echo "helm uninstall ${RELEASE_NAME}      # Uninstall"
    echo ""
}

# Main execution
main() {
    echo ""
    check_prerequisites
    echo ""
    start_minikube
    echo ""
    build_image
    echo ""
    check_victoriametrics
    echo ""
    deploy_helm
    echo ""
    wait_for_deployment
    echo ""
    get_access_info
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --clean)
            print_status "Cleaning up existing deployment..."
            helm uninstall ${RELEASE_NAME} 2>/dev/null || true
            shift
            ;;
        --help)
            echo "Usage: $0 [--clean] [--help]"
            echo "  --clean    Clean up existing deployment before installing"
            echo "  --help     Show this help message"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Run main function
main
