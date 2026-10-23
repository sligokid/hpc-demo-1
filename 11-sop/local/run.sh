#!/bin/bash
# Run sop.py locally for a single transcript/analysis pair.
#
# Usage:
#   bash 11-sop/local/run.sh results/en/myvideo
#
# This will read:
#   results/en/myvideo.transcript.txt
#   results/en/myvideo.analysis.json
# And write:
#   results/en/myvideo.sop.md
#   results/en/myvideo.sop.pdf

set -euo pipefail

STEM=${1:?Usage: bash 11-sop/local/run.sh <output_stem>}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

MODEL=${MODEL:-qwen2.5:7b}
OLLAMA_HOST=${OLLAMA_HOST:-localhost:11434}
CONFIG=${CONFIG:-"$PROJECT_ROOT/11-sop/sop_config.yaml"}

python "$PROJECT_ROOT/11-sop/sop.py" \
    --transcript "${STEM}.transcript.txt" \
    --analysis   "${STEM}.analysis.json" \
    --output     "$STEM" \
    --config     "$CONFIG" \
    --ollama-host "$OLLAMA_HOST" \
    --model      "$MODEL"
