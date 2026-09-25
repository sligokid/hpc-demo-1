#!/bin/bash

# Build and push the amd64 Docker image
#

cd ../..
docker buildx build --platform linux/amd64 -t sligokid/embeddings-api:latest --push -f 5-embed/docker/Dockerfile .