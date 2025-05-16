#!/bin/bash
# Script to build and push Docker images

# Set variables
IMAGE_NAME="llamasearch/openmanufacturing"
VERSION=$(grep -m 1 "version" setup.py | cut -d'"' -f2)
TAG_LATEST="${IMAGE_NAME}:latest"
TAG_VERSION="${IMAGE_NAME}:${VERSION}"

# Ensure we're logged in
./docker-login.sh

# Build the Docker image
echo "Building Docker image..."
docker build -t $TAG_LATEST -t $TAG_VERSION -f Dockerfile.new .

# Push to Docker Hub
echo "Pushing to Docker Hub..."
docker push $TAG_LATEST
docker push $TAG_VERSION

echo "Done! Images pushed to Docker Hub."
echo "  ${TAG_LATEST}"
echo "  ${TAG_VERSION}" 