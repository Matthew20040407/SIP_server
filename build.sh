#!/bin/bash
set -e

git pull

IMAGE_NAME="sip-server-v2"
BRANCH=$(git rev-parse --abbrev-ref HEAD)
BRANCH_TAG="${BRANCH//feature\//}"
IMAGE_TAG="${1:-$([ "$BRANCH" = "main" ] && echo "latest" || echo "$BRANCH_TAG")}"

echo "Building Docker image: ${IMAGE_NAME}:${IMAGE_TAG}"
docker build -t "${IMAGE_NAME}:${IMAGE_TAG}" .

echo "Build complete: ${IMAGE_NAME}:${IMAGE_TAG}"

echo "> Stopping old container..."
docker stop ${IMAGE_NAME} 2>/dev/null || true
docker rm ${IMAGE_NAME} 2>/dev/null || true
echo "> Container deleted"

echo "> Starting new container..."
IMAGE_TAG="${IMAGE_TAG}" docker compose up -d

echo "> Deployment complete!"