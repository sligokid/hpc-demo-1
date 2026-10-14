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

SIF=/scratch/project_465003359/mcgowank/agent.sif
HF_HOME="${HF_HOME:-/root/.cache/huggingface}"
QDRANT_HOST="${QDRANT_HOST:-localhost:6333}"
OLLAMA_HOST="${OLLAMA_HOST:-localhost:11434}"
AGENT_MODEL="${AGENT_MODEL:-qwen2.5:3b}"
EMBED_MODEL="${EMBED_MODEL:-intfloat/multilingual-e5-large}"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "PROJECT_ROOT : $PROJECT_ROOT"
echo "SIF          : $SIF"
echo "QDRANT_HOST  : $QDRANT_HOST"
echo "OLLAMA_HOST  : $OLLAMA_HOST"
echo "AGENT_MODEL    : $AGENT_MODEL"
echo ""

singularity exec \
    --bind "$PROJECT_ROOT:/workspace" \
    --bind "$PROJECT_ROOT/.hf_cache:$HF_HOME" \
    --env QDRANT_HOST="$QDRANT_HOST" \
    --env OLLAMA_HOST="$OLLAMA_HOST" \
    --env AGENT_MODEL="$AGENT_MODEL" \
    --env EMBED_MODEL="$EMBED_MODEL" \
    --env HF_HOME="$HF_HOME" \
    "$SIF" bash -c "
export LD_LIBRARY_PATH=/opt/rocm/lib:/opt/rocm/lib64:/usr/local/lib
python /workspace/10-agent/agent.py
"
