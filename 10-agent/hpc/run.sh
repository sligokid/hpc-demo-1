#!/usr/bin/env bash
# Interactive srun: run the RAG agent inside the Singularity image.
# Uses BASH_SOURCE to resolve PROJECT_ROOT correctly regardless of the
# working directory at call time (srun interactive pattern — not SLURM_SUBMIT_DIR).
#
# Usage (inside an srun interactive session):
#   export QDRANT_HOST=localhost:6333
#   export OLLAMA_HOST=localhost:11434
#   bash 10-agent/hpc/run.sh
#
# Or from anywhere:
#   bash /path/to/10-agent/hpc/run.sh

set -euo pipefail

SCRATCH=${SCRATCH:-/scratch/project_465003359/mcgowank}
SIF=${SIF:-$SCRATCH/agent.sif}
HF_CACHE=${HF_CACHE:-$SCRATCH/hf_cache}
QDRANT_HOST="${QDRANT_HOST:-localhost:6333}"
OLLAMA_HOST="${OLLAMA_HOST:-localhost:11434}"
AGENT_MODEL="${AGENT_MODEL:-qwen2.5:3b}"
EMBED_MODEL="${EMBED_MODEL:-intfloat/multilingual-e5-large}"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

mkdir -p "$HF_CACHE"

echo "PROJECT_ROOT : $PROJECT_ROOT"
echo "SIF          : $SIF"
echo "HF_CACHE     : $HF_CACHE"
echo "QDRANT_HOST  : $QDRANT_HOST"
echo "OLLAMA_HOST  : $OLLAMA_HOST"
echo "AGENT_MODEL  : $AGENT_MODEL"
echo ""

singularity exec \
    --bind "$PROJECT_ROOT:/workspace" \
    --bind "$HF_CACHE:/hf_cache" \
    --env QDRANT_HOST="$QDRANT_HOST" \
    --env OLLAMA_HOST="$OLLAMA_HOST" \
    --env AGENT_MODEL="$AGENT_MODEL" \
    --env EMBED_MODEL="$EMBED_MODEL" \
    --env HF_HOME=/hf_cache \
    "$SIF" bash -c "
export LD_LIBRARY_PATH=/opt/rocm/lib:/opt/rocm/lib64:/usr/local/lib
python /workspace/10-agent/agent.py
"
