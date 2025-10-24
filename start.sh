#!/bin/bash

IMAGE_NAME="21441677/demo:latest"

echo "Starting Docker container update..."

echo "Pulling latest image..."
docker pull $IMAGE_NAME

if [ $? -ne 0 ]; then
    echo "Image pull failed"
    exit 1
fi

echo "Image pulled successfully"

echo "Stopping running containers..."
CONTAINER_IDS=$(docker ps -q --filter publish=8000)

if [ -n "$CONTAINER_IDS" ]; then
    docker stop $CONTAINER_IDS
    echo "Stopped containers: $CONTAINER_IDS"

    docker rm $CONTAINER_IDS
    echo "Removed containers: $CONTAINER_IDS"
else
    echo "No running containers found"
fi

echo "Cleaning up dangling images..."
docker image prune -f

echo "Starting new container..."
docker run -d -p 8000:8000 $IMAGE_NAME

if [ $? -eq 0 ]; then
    echo "Container started successfully"
    echo "Application is running at http://localhost:8000"
else
    echo "Container failed to start"
    exit 1
fi

echo "Update complete"
