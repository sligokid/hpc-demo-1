#!/bin/bash

# Build and push the whisper-hpc Docker image
docker buildx build --platform linux/amd64 -t sligokid/whisper-hpc:test -f Dockerfile . --push 

# Build and push the whisper-sync Docker image
docker buildx build --platform linux/amd64 -t sligokid/whisper-sync:test -f 4-file-sync/Dockerfile 4-file-sync/ --push

# Build and push the embeddings-api Docker image
docker buildx build --platform linux/amd64 -t sligokid/embeddings-api:test -f 5-embed/docker/Dockerfile . --push