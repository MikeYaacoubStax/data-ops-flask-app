#!/bin/bash
set -e

echo "🔧 Fixing and updating NoSQLBench Demo deployment..."

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Set minikube docker environment
print_status "Setting minikube docker environment..."
eval $(minikube docker-env)

# Rebuild the webapp image
print_status "Rebuilding webapp image with fixes..."
cd docker
docker build -t nosqlbench-webapp:v1.0.0 .
cd ..

# Upgrade the Helm release
print_status "Upgrading Helm release with RBAC and command fixes..."
helm upgrade nosqlbench-demo . -f test-values.yaml

# Wait for rollout
print_status "Waiting for deployment rollout..."
kubectl rollout status deployment/nosqlbench-demo --timeout=120s

# Check pod status
print_status "Checking pod status..."
kubectl get pods -l app.kubernetes.io/name=nosqlbench-demo

print_success "Update completed! Check the logs:"
echo "kubectl logs -l app.kubernetes.io/name=nosqlbench-demo --tail=20"

# Get service URL
SERVICE_URL=$(minikube service nosqlbench-demo --url)
print_success "Web interface: ${SERVICE_URL}"
