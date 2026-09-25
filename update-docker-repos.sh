#!/bin/bash

# # Build and push the whisper-hpc Docker image
# docker buildx build --platform linux/amd64 -t sligokid/whisper-hpc:latest . --push

# # Build and push the whisper-sync Docker image
# docker buildx build --platform linux/amd64 -t sligokid/whisper-sync:latest -f 4-file-sync/Dockerfile 4-file-sync/ --push

# # Build and push the embeddings-api Docker image
# docker buildx build --platform linux/amd64 -t sligokid/embeddings-api:latest -f 5-embed/docker/Dockerfile . --push