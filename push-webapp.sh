#!/bin/bash
set -e

# Docker Hub repository configuration
DOCKER_REPO="mikeyaacoubstax/mike-personal"

# Image configuration
IMAGE_NAME="nosqlbench-webapp"
IMAGE_TAG="${1:-latest}"  # Use first argument as tag, default to 'latest'
FULL_IMAGE_NAME="${DOCKER_REPO}:${IMAGE_TAG}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 NoSQLBench Webapp Docker Push Script${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""
echo -e "${YELLOW}Configuration:${NC}"
echo -e "  Repository: ${DOCKER_REPO}"
echo -e "  Image Tag: ${IMAGE_TAG}"
echo -e "  Full Image Name: ${FULL_IMAGE_NAME}"
echo ""

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo -e "${RED}❌ Error: Docker is not running. Please start Docker and try again.${NC}"
    exit 1
fi

# Check if helm/docker directory exists
if [ ! -d "helm/docker" ]; then
    echo -e "${RED}❌ Error: helm/docker directory not found. Please run this script from the project root.${NC}"
    exit 1
fi

# Check if Dockerfile exists
if [ ! -f "helm/docker/Dockerfile" ]; then
    echo -e "${RED}❌ Error: Dockerfile not found in helm/docker/. Cannot build image.${NC}"
    exit 1
fi

echo -e "${YELLOW}🔐 Checking Docker Hub authentication...${NC}"
# Check if user is logged into Docker Hub by trying to access user info
if ! docker system info | grep -q "Username:"; then
    echo -e "${RED}❌ Not logged into Docker Hub. Please run 'docker login' first.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker Hub authentication confirmed${NC}"
echo ""

echo -e "${YELLOW}🏗️  Building Docker image...${NC}"
echo -e "Building from: helm/docker/"
echo -e "Image: ${FULL_IMAGE_NAME}"
echo ""

# Build the Docker image from the helm/docker directory
cd helm/docker
docker build -t "$FULL_IMAGE_NAME" .

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to build Docker image${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Successfully built Docker image: ${FULL_IMAGE_NAME}${NC}"
echo ""

echo -e "${YELLOW}📤 Pushing image to Docker Hub...${NC}"
docker push "$FULL_IMAGE_NAME"

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to push Docker image${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Successfully pushed image: ${FULL_IMAGE_NAME}${NC}"
echo ""

# Also tag and push as 'latest' if a specific tag was provided
if [ "$IMAGE_TAG" != "latest" ]; then
    LATEST_IMAGE_NAME="${DOCKER_REPO}:latest"
    echo -e "${YELLOW}🏷️  Tagging as latest...${NC}"
    docker tag "$FULL_IMAGE_NAME" "$LATEST_IMAGE_NAME"
    
    echo -e "${YELLOW}📤 Pushing latest tag...${NC}"
    docker push "$LATEST_IMAGE_NAME"
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Successfully pushed latest tag: ${LATEST_IMAGE_NAME}${NC}"
    else
        echo -e "${YELLOW}⚠️  Warning: Failed to push latest tag, but main tag was successful${NC}"
    fi
    echo ""
fi

echo -e "${YELLOW}🧹 Cleaning up...${NC}"
# Clean up any dangling images (optional)
docker image prune -f --filter "dangling=true" >/dev/null 2>&1 || true

echo -e "${GREEN}✅ Cleanup completed${NC}"
echo ""

echo -e "${BLUE}🎉 Push completed successfully!${NC}"
echo -e "${BLUE}================================${NC}"
echo ""
echo -e "${GREEN}Your webapp image is now available at:${NC}"
echo -e "  ${FULL_IMAGE_NAME}"
if [ "$IMAGE_TAG" != "latest" ]; then
    echo -e "  ${DOCKER_REPO}:latest"
fi
echo ""
echo -e "${YELLOW}To use this image in your Helm chart:${NC}"
echo -e "  helm install nosqlbench-demo ./helm \\"
echo -e "    --set webapp.image.repository=${DOCKER_REPO} \\"
echo -e "    --set webapp.image.tag=${IMAGE_TAG}"
echo ""
echo -e "${YELLOW}To pull and run locally:${NC}"
echo -e "  docker pull ${FULL_IMAGE_NAME}"
echo -e "  docker run -p 5000:5000 ${FULL_IMAGE_NAME}"
echo ""
