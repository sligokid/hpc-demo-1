#!/usr/bin/env bash
# Start the embedding server. Loads multilingual-e5-large once and serves
# POST /embed on port 8765.
# Run from the project root with the venv active.
set -euo pipefail

cd "$(dirname "$0")/../.."

python 6-embed/embed_server.py --port 8765
