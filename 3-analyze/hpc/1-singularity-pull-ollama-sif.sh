SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
[ -f "$PROJECT_ROOT/.env" ] && source "$PROJECT_ROOT/.env"
SCRATCH=${HPC_SCRATCH:?".env must define HPC_SCRATCH"}
OLLAMA_SIF=${OLLAMA_SIF:-$SCRATCH/ollama.sif}

singularity pull $OLLAMA_SIF docker://ollama/ollama:rocm
