#!/usr/bin/env bash
# End-to-end pipeline run on a single sample audio file.
# Prerequisites: Qdrant running (script 1), embed-server running (script 2),
# Ollama running with llama3 pulled, venv active.
# Run from the project root.
set -euo pipefail

cd "$(dirname "$0")/../.."

AUDIO="${1:-2-inference/audio/sligo-triathlon-club-inviting-women-to-try-a-tri.mp3}"
LANG="${2:-en}"

python pipeline.py --file "$AUDIO" --lang "$LANG"
