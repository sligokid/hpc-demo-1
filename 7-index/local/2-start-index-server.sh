#!/usr/bin/env bash
# Start the index server. Receives vectors from embed-server and writes to Qdrant.
# Serves POST /index and POST /metadata on port 8766.
# Run from the project root with the venv active.
set -euo pipefail

cd "$(dirname "$0")/../.."

python 7-index/index_server.py --qdrant-host localhost:6333 --port 8766
