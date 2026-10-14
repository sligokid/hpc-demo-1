#!/usr/bin/env bash
# Launch the HPC video knowledge-base agent locally.
# Reads env vars from local/.env (copied from local/.env.example).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"

if [[ -f "$ENV_FILE" ]]; then
    set -o allexport
    # shellcheck source=/dev/null
    source "$ENV_FILE"
    set +o allexport
fi

export QDRANT_HOST="${QDRANT_HOST:-localhost:6333}"
export OLLAMA_HOST="${OLLAMA_HOST:-localhost:11434}"
export AGENT_MODEL="${AGENT_MODEL:-qwen2.5:3b}"
export EMBED_MODEL="${EMBED_MODEL:-intfloat/multilingual-e5-large}"
export HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}"

cd "$AGENT_DIR"
python agent.py
