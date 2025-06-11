#!/bin/bash
set -e

# Build script for NoSQLBench Kubernetes Demo webapp

# Configuration
IMAGE_NAME="nosqlbench-webapp"
IMAGE_TAG="latest"
REGISTRY=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --tag)
            IMAGE_TAG="$2"
            shift 2
            ;;
        --registry)
            REGISTRY="$2"
            shift 2
            ;;
        --push)
            PUSH_IMAGE=true
            shift
            ;;
        --help)
            echo "Usage: $0 [--tag TAG] [--registry REGISTRY] [--push]"
            echo "  --tag TAG        Set image tag (default: latest)"
            echo "  --registry REG   Set registry prefix"
            echo "  --push          Push image after building"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Build full image name
if [ -n "$REGISTRY" ]; then
    FULL_IMAGE_NAME="${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
else
    FULL_IMAGE_NAME="${IMAGE_NAME}:${IMAGE_TAG}"
fi

echo "Building NoSQLBench Kubernetes Demo webapp..."
echo "Image: $FULL_IMAGE_NAME"

# Build the Docker image
docker build -t "$FULL_IMAGE_NAME" .

echo "✅ Build completed successfully!"
echo "Image: $FULL_IMAGE_NAME"

# Push if requested
if [ "$PUSH_IMAGE" = true ]; then
    echo "Pushing image to registry..."
    docker push "$FULL_IMAGE_NAME"
    echo "✅ Push completed successfully!"
fi

echo ""
echo "To use this image in your Helm chart:"
echo "  helm install nosqlbench-demo ../helm \\"
echo "    --set webapp.image.repository=$IMAGE_NAME \\"
echo "    --set webapp.image.tag=$IMAGE_TAG \\"
if [ -n "$REGISTRY" ]; then
echo "    --set webapp.image.registry=$REGISTRY \\"
fi
echo "    --set databases.cassandra.enabled=true \\"
echo "    --set databases.cassandra.host=your-cassandra-host"
