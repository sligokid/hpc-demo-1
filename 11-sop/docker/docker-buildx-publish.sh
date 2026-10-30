#!/bin/bash

# Build and push the amd64 Docker image
#

cd ../..
docker buildx build --platform linux/amd64 -t sligokid/sop-tools:latest --push -f 11-sop/docker/Dockerfile .
