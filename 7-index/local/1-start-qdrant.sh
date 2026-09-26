#!/usr/bin/env bash
# Start a local Qdrant instance on port 6333 using Docker.
# Data is stored in a named volume so it persists across restarts.
set -euo pipefail

docker run -d \
  --name qdrant \
  -p 6333:6333 \
  -p 6334:6334 \
  -v qdrant_storage:/qdrant/storage \
  qdrant/qdrant

echo "Qdrant started at http://localhost:6333"
echo "Dashboard: http://localhost:6333/dashboard"
