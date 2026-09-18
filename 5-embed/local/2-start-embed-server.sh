#!/usr/bin/env bash
# Start the embedding server. Loads multilingual-e5-large once and serves
# POST /embed and POST /metadata on port 8765.
# Run from the project root with the venv active.
set -euo pipefail

cd "$(dirname "$0")/../.."

python 5-embed/embed-server.py --qdrant-host localhost:6333 --port 8765
