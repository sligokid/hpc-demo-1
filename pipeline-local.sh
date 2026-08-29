#!/bin/bash
# Run the full pipeline locally (infer -> analyze).
# Ollama must already be running: ollama serve
#
# Usage:
#   ./pipeline-local.sh
#   ./pipeline-local.sh --lang en
#   ./pipeline-local.sh --ollama-host localhost:11434

set -euo pipefail

cd "$(dirname "$0")"
source venv/bin/activate

python pipeline.py "$@"
