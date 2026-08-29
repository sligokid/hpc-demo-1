#!/bin/bash
# Run the full pipeline in Docker (infer -> analyze).
# Ollama must already be running: docker compose up ollama -d
#
# Usage:
#   ./pipeline-docker.sh
#   ./pipeline-docker.sh --lang en

set -euo pipefail

cd "$(dirname "$0")"

docker compose run --rm dev python pipeline.py --ollama-host host.docker.internal:11434 "$@"
