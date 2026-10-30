#!/bin/bash
# Run tts.py locally for a single teleprompter file.
#
# Usage:
#   bash 12-tts/local/run.sh results/en/myvideo.teleprompter.md
#
# This will read:
#   results/en/myvideo.teleprompter.md
# And write:
#   results/en/myvideo.teleprompter.wav
#
# Environment variables:
#   OLLAMA_HOST   host:port for Ollama  (default: localhost:11434)
#   VOICE         TTS voice name        (default: male)

set -euo pipefail

TELEPROMPTER_FILE=${1:?Usage: bash 12-tts/local/run.sh <teleprompter-file>}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

OLLAMA_HOST=${OLLAMA_HOST:-localhost:11434}
VOICE=${VOICE:-male}
MODEL=${MODEL:-lfm3-audio}

LANG=$(basename "$(dirname "$TELEPROMPTER_FILE")")
STEM=$(basename "$TELEPROMPTER_FILE" .teleprompter.md)
OUTPUT_STEM="$(dirname "$TELEPROMPTER_FILE")/$STEM"

python "$PROJECT_ROOT/12-tts/tts.py" \
    --input       "$TELEPROMPTER_FILE" \
    --output      "$OUTPUT_STEM" \
    --ollama-host "$OLLAMA_HOST" \
    --voice       "$VOICE" \
    --model       "$MODEL"
