#!/usr/bin/env bash
# Build the agent image as slickplus/agent:latest.
# Run from anywhere — script resolves the project root automatically.
set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../.."

docker buildx build \
    --platform linux/amd64 \
    -t slickplus/agent:latest \
    -f 10-agent/docker/Dockerfile \
    .
