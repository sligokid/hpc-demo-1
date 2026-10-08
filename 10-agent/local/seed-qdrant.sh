#!/usr/bin/env bash
# Seed Qdrant from HPC pipeline output files in sync/output/.
#
# Pre-requisites (must be running):
#   7-index/local/1-start-qdrant.sh
#   6-embed/local/1-start-embed-server.sh
#   7-index/local/2-start-index-server.sh
#
# Usage:
#   ./10-agent/local/seed-qdrant.sh               # all languages
#   ./10-agent/local/seed-qdrant.sh --lang en     # single language
#   ./10-agent/local/seed-qdrant.sh --force       # re-index existing
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

source "$PROJECT_ROOT/venv/bin/activate"

python "$PROJECT_ROOT/seed_qdrant.py" --out-dir "$PROJECT_ROOT/sync/output" "$@"
