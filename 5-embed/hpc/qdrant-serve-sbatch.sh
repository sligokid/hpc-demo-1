#!/bin/bash
# Persistent Qdrant vector-database service on a GPU node.
#
# Pull the SIF once before submitting (from a login node with internet access):
#   singularity pull /scratch/project_465003209/mcgowank/qdrant.sif docker://qdrant/qdrant:latest
#
# Submit:
#   sbatch 5-embed/hpc/qdrant-serve-sbatch.sh
#
# Chain with the embedding service:
#   JID=$(sbatch --parsable 5-embed/hpc/qdrant-serve-sbatch.sh)
#   sbatch --dependency=after:$JID 5-embed/hpc/embeddings-serve-sbatch.sh

#SBATCH --job-name=D-qdrant
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=08:00:00
#SBATCH --output=logs/qdrant-slurm-%j.out
#SBATCH --error=logs/qdrant-slurm-%j.err
#SBATCH --account=project_465003209
#SBATCH --partition=small-g

set -euo pipefail

# --- Configuration (edit here) ---
QDRANT_PORT=6333
HEALTH_TIMEOUT=120                    # seconds to wait for Qdrant to be ready
SCRATCH=${SCRATCH:-/scratch/project_465003209/mcgowank}
QDRANT_SIF=${QDRANT_SIF:-$SCRATCH/qdrant.sif}
QDRANT_STORAGE_DIR=$SCRATCH/qdrant-storage
ENDPOINT_FILE=$SCRATCH/qdrant.endpoint
# ----------------------------------

# Resolve project root whether sbatch was called from the project root or
# from within 5-embed/hpc/.
if [ -f "$SLURM_SUBMIT_DIR/pipeline.yaml" ]; then
    PROJECT_ROOT="$(cd "$SLURM_SUBMIT_DIR" && pwd)"
else
    PROJECT_ROOT="$(cd "$SLURM_SUBMIT_DIR/../.." && pwd)"
fi
mkdir -p "$PROJECT_ROOT/logs" "$QDRANT_STORAGE_DIR"

echo "============================================"
echo "Job ID   : $SLURM_JOB_ID"
echo "Node     : $(hostname)"
echo "GPU      : $(rocm-smi --showproductname 2>/dev/null | grep 'Card Series' | head -1 || echo 'unknown')"
echo "SIF      : $QDRANT_SIF"
echo "Port     : $QDRANT_PORT"
echo "Storage  : $QDRANT_STORAGE_DIR"
echo "Endpoint : $ENDPOINT_FILE"
echo "============================================"

# Clean up endpoint file on exit.
trap 'rm -f "$ENDPOINT_FILE"' EXIT

# Fail fast if port is already in use on this node
if ss -tlnp 2>/dev/null | grep -q ":${QDRANT_PORT} "; then
    echo "Error: port ${QDRANT_PORT} is already in use on $(hostname). Re-submit or choose a different port." >&2
    exit 1
fi

# Start Qdrant inside Singularity in the background.
# bash -c ensures LD_LIBRARY_PATH is exported inside the container.
singularity exec \
    --rocm \
    --bind "$QDRANT_STORAGE_DIR:/qdrant/storage" \
    --env QDRANT__SERVICE__HTTP_PORT=${QDRANT_PORT} \
    "$QDRANT_SIF" \
    bash -c "
        export LD_LIBRARY_PATH=/opt/rocm/lib:/opt/rocm/lib64:/usr/local/lib
        /qdrant/qdrant
    " &
QDRANT_PID=$!

echo "Qdrant PID: $QDRANT_PID"

# Health-check loop: poll /healthz until 200 OK or timeout
echo "Waiting for Qdrant to become ready (timeout ${HEALTH_TIMEOUT}s)..."
ELAPSED=0
until curl -sf "http://localhost:${QDRANT_PORT}/healthz" > /dev/null 2>&1; do
    if [ "$ELAPSED" -ge "$HEALTH_TIMEOUT" ]; then
        echo "Error: Qdrant did not become ready within ${HEALTH_TIMEOUT}s on $(hostname):${QDRANT_PORT}" >&2
        exit 1
    fi
    sleep 2
    ELAPSED=$((ELAPSED + 2))
done

echo "Qdrant is ready after ${ELAPSED}s."

# Write endpoint file atomically
TMPFILE=$(mktemp "${ENDPOINT_FILE}.XXXXXX")
echo "$(hostname):${QDRANT_PORT}" > "$TMPFILE"
mv "$TMPFILE" "$ENDPOINT_FILE"

echo "Endpoint written: $(cat "$ENDPOINT_FILE")"

# Keep the job alive until wall time or the Qdrant process exits
wait "$QDRANT_PID"
