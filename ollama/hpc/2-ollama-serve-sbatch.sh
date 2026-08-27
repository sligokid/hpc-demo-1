#!/bin/bash
# Persistent Ollama inference service on a GPU node.
#
# Build ollama.sif once (on a node with internet access or from a login node):
#   singularity pull ollama.sif docker://ollama/ollama:rocm
#
# Submit:
#   sbatch ollama-serve.sh
#
# Chain with analysis jobs:
#   JID=$(sbatch --parsable ollama-serve.sh)
#   sbatch --dependency=after:$JID analyze-batch.sh
#
# HITL gate: validate that the ROCm version bundled in ollama.sif is
# compatible with the cluster driver before running in production.
# Check with: singularity run ollama.sif -- rocm-smi --version

#SBATCH --job-name=ollama-serve
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=08:00:00
#SBATCH --output=logs/%j.out
#SBATCH --error=logs/%j.err
#SBATCH --account=project_465003209
#SBATCH --partition=small-g

set -euo pipefail

# --- Configuration (edit here) ---
WALL_TIME=08:00:00                    # must match #SBATCH --time above
OLLAMA_PORT=11434
HEALTH_TIMEOUT=120                    # seconds to wait for Ollama to be ready
SCRATCH=/scratch/project_465003209/mcgowank
OLLAMA_SIF=${OLLAMA_SIF:-$SCRATCH/ollama.sif}
OLLAMA_MODELS_DIR=$SCRATCH/ollama-models
ENDPOINT_FILE=$SCRATCH/ollama.endpoint
# ----------------------------------

mkdir -p logs "$OLLAMA_MODELS_DIR"

echo "============================================"
echo "Job ID   : $SLURM_JOB_ID"
echo "Node     : $(hostname)"
echo "GPU      : $(rocm-smi --showproductname 2>/dev/null | grep 'Card Series' | head -1 || echo 'unknown')"
echo "SIF      : $OLLAMA_SIF"
echo "Port     : $OLLAMA_PORT"
echo "Endpoint : $ENDPOINT_FILE"
echo "============================================"

# Remove discovery file on any exit so stale endpoints don't mislead future jobs
cleanup() {
    echo "Cleaning up endpoint file..."
    rm -f "$ENDPOINT_FILE"
}
trap cleanup EXIT

# Fail fast if port is already in use on this node
if ss -tlnp 2>/dev/null | grep -q ":${OLLAMA_PORT} "; then
    echo "Error: port ${OLLAMA_PORT} is already in use on $(hostname). Re-submit or choose a different port." >&2
    exit 1
fi

# Start Ollama server inside Singularity in the background
OLLAMA_HOST=0.0.0.0:${OLLAMA_PORT} \
singularity run \
    --rocm \
    --bind "$OLLAMA_MODELS_DIR:/ollama-models" \
    --env OLLAMA_MODELS=/ollama-models \
    --env OLLAMA_HOST=0.0.0.0:${OLLAMA_PORT} \
    "$OLLAMA_SIF" serve &
OLLAMA_PID=$!

echo "Ollama PID: $OLLAMA_PID"

# Health-check loop: poll /api/tags until 200 OK or timeout
echo "Waiting for Ollama to become ready (timeout ${HEALTH_TIMEOUT}s)..."
ELAPSED=0
until curl -sf "http://localhost:${OLLAMA_PORT}/api/tags" > /dev/null 2>&1; do
    if [ "$ELAPSED" -ge "$HEALTH_TIMEOUT" ]; then
        echo "Error: Ollama did not become ready within ${HEALTH_TIMEOUT}s on $(hostname):${OLLAMA_PORT}" >&2
        exit 1
    fi
    sleep 2
    ELAPSED=$((ELAPSED + 2))
done

echo "Ollama is ready after ${ELAPSED}s."

# Write endpoint file atomically
TMPFILE=$(mktemp "${ENDPOINT_FILE}.XXXXXX")
echo "$(hostname):${OLLAMA_PORT}" > "$TMPFILE"
mv "$TMPFILE" "$ENDPOINT_FILE"

echo "Endpoint written: $(cat "$ENDPOINT_FILE")"

# Keep the job alive until wall time or the Ollama process exits
wait "$OLLAMA_PID"
