#!/bin/bash
# Run teleprompter.py locally for a single SOP file.
#
# Usage:
#   bash 11-sop/local/run-teleprompter.sh inbox/en/my-procedure.sop.md
#
# This will read:
#   inbox/en/my-procedure.sop.md
# And write:
#   results/en/my-procedure.teleprompter.md
#   results/en/my-procedure.teleprompter.review.md

set -euo pipefail

SOP_FILE=${1:?Usage: bash 11-sop/local/run-teleprompter.sh <sop-file>}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

MODEL=${MODEL:-qwen2.5:7b}
OLLAMA_HOST=${OLLAMA_HOST:-localhost:11434}

# Derive output stem: inbox/{lang}/{stem}.sop.md -> results/{lang}/{stem}
LANG=$(basename "$(dirname "$SOP_FILE")")
STEM=$(basename "$SOP_FILE" .sop.md)
STEM=$(basename "$STEM" .md)
OUTPUT_STEM="$PROJECT_ROOT/results/$LANG/$STEM"
mkdir -p "$PROJECT_ROOT/results/$LANG"

python "$PROJECT_ROOT/11-sop/teleprompter.py" \
    --sop         "$SOP_FILE" \
    --output      "$OUTPUT_STEM" \
    --ollama-host "$OLLAMA_HOST" \
    --model       "$MODEL"
