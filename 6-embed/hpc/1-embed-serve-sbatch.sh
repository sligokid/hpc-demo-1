#!/bin/bash
# Persistent embedding server service on a GPU node.
# Loads intfloat/multilingual-e5-large once and serves POST /embed on port 8765.
# Returns raw vectors — no Qdrant dependency.
#
# Prerequisites:
#   SIF pulled:
#     singularity pull /scratch/project_465003359/mcgowank/embeddings-api.sif docker://sligokid/embeddings-api:latest
#
# Submit:
#   sbatch 6-embed/hpc/1-embed-serve-sbatch.sh
#
# Chain with the index service job:
#   JID=$(sbatch --parsable 6-embed/hpc/1-embed-serve-sbatch.sh)
#   sbatch --dependency=after:$JID 7-index/hpc/2-index-serve-sbatch.sh

#SBATCH --job-name=D-embed
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=08:00:00
#SBATCH --output=logs/embed-slurm-%j.out
#SBATCH --error=logs/embed-slurm-%j.err
#SBATCH --account=project_465003359
#SBATCH --partition=small-g

set -euo pipefail

# --- Configuration (edit here) ---
EMBED_PORT=8765
HEALTH_TIMEOUT=180                    # seconds to wait for model load + server ready
SCRATCH=${SCRATCH:-/scratch/project_465003359/mcgowank}
EMBEDDINGS_SIF=${EMBEDDINGS_SIF:-$SCRATCH/embeddings-api.sif}
EMBED_ENDPOINT_FILE=$SCRATCH/embed.endpoint
# ----------------------------------

# Resolve project root whether sbatch was called from the project root or
# from within 6-embed/hpc/.
if [ -f "$SLURM_SUBMIT_DIR/pipeline.yaml" ]; then
    PROJECT_ROOT="$(cd "$SLURM_SUBMIT_DIR" && pwd)"
else
    PROJECT_ROOT="$(cd "$SLURM_SUBMIT_DIR/../.." && pwd)"
fi
mkdir -p "$PROJECT_ROOT/logs"

echo "============================================"
echo "Job ID   : $SLURM_JOB_ID"
echo "Node     : $(hostname)"
echo "GPU      : $(rocm-smi --showproductname 2>/dev/null | grep 'Card Series' | head -1 || echo 'unknown')"
echo "SIF      : $EMBEDDINGS_SIF"
echo "Port     : $EMBED_PORT"
echo "============================================"

# Clean up endpoint file on exit.
trap 'rm -f "$EMBED_ENDPOINT_FILE"' EXIT

# Fail fast if port is already in use on this node
if ss -tlnp 2>/dev/null | grep -q ":${EMBED_PORT} "; then
    echo "Error: port ${EMBED_PORT} is already in use on $(hostname). Re-submit or choose a different port." >&2
    exit 1
fi

# Start embed-server inside Singularity in the background.
# bash -c ensures LD_LIBRARY_PATH is exported inside the container.
singularity exec \
    --rocm \
    --bind "$PROJECT_ROOT:/workspace" \
    "$EMBEDDINGS_SIF" \
    bash -c "
        export LD_LIBRARY_PATH=/opt/rocm/lib:/opt/rocm/lib64:/usr/local/lib
        python /workspace/6-embed/embed_server.py \
            --port ${EMBED_PORT}
    " &
EMBED_PID=$!

echo "Embed server PID: $EMBED_PID"

# Health-check loop: poll /health until 200 OK or timeout
echo "Waiting for embed-server to become ready (timeout ${HEALTH_TIMEOUT}s)..."
ELAPSED=0
until curl -sf "http://localhost:${EMBED_PORT}/health" > /dev/null 2>&1; do
    if [ "$ELAPSED" -ge "$HEALTH_TIMEOUT" ]; then
        echo "Error: embed-server did not become ready within ${HEALTH_TIMEOUT}s on $(hostname):${EMBED_PORT}" >&2
        exit 1
    fi
    sleep 5
    ELAPSED=$((ELAPSED + 5))
done

echo "Embed server is ready after ${ELAPSED}s."

# Write endpoint file atomically
TMPFILE=$(mktemp "${EMBED_ENDPOINT_FILE}.XXXXXX")
echo "$(hostname):${EMBED_PORT}" > "$TMPFILE"
mv "$TMPFILE" "$EMBED_ENDPOINT_FILE"

echo "Endpoint written: $(cat "$EMBED_ENDPOINT_FILE")"

# Keep the job alive until wall time or the embed-server process exits
wait "$EMBED_PID"
