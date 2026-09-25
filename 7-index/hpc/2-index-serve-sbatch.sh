#!/bin/bash
# Persistent index server service on a CPU node.
# Receives pre-computed vectors and writes to Qdrant on port 8766.
# No model dependency — lightweight CPU job.
#
# Prerequisites:
#   1. qdrant-serve-sbatch.sh is running and has written the endpoint file
#   2. embeddings-api.sif pulled (shared with 6-embed):
#      singularity pull /scratch/project_465003359/mcgowank/embeddings-api.sif docker://sligokid/embeddings-api:latest
#
# Submit:
#   sbatch 7-index/hpc/2-index-serve-sbatch.sh
#
# Chain with Qdrant:
#   JID=$(sbatch --parsable 7-index/hpc/1-qdrant-serve-sbatch.sh)
#   sbatch --dependency=after:$JID 7-index/hpc/2-index-serve-sbatch.sh

#SBATCH --job-name=I-index
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=08:00:00
#SBATCH --output=logs/index-slurm-%j.out
#SBATCH --error=logs/index-slurm-%j.err
#SBATCH --account=project_465003359
#SBATCH --partition=small

set -euo pipefail

# --- Configuration (edit here) ---
INDEX_PORT=8766
HEALTH_TIMEOUT=60
SCRATCH=${SCRATCH:-/scratch/project_465003359/mcgowank}
EMBEDDINGS_SIF=${EMBEDDINGS_SIF:-$SCRATCH/embeddings-api.sif}
QDRANT_ENDPOINT_FILE=$SCRATCH/qdrant.endpoint
INDEX_ENDPOINT_FILE=$SCRATCH/index.endpoint
# ----------------------------------

# Resolve project root whether sbatch was called from the project root or
# from within 7-index/hpc/.
if [ -f "$SLURM_SUBMIT_DIR/pipeline.yaml" ]; then
    PROJECT_ROOT="$(cd "$SLURM_SUBMIT_DIR" && pwd)"
else
    PROJECT_ROOT="$(cd "$SLURM_SUBMIT_DIR/../.." && pwd)"
fi
mkdir -p "$PROJECT_ROOT/logs"

# Fail fast if the Qdrant service is not running
if [ ! -f "$QDRANT_ENDPOINT_FILE" ]; then
    echo "Error: Qdrant endpoint file not found at $QDRANT_ENDPOINT_FILE" >&2
    echo "Start the Qdrant service first: sbatch 7-index/hpc/1-qdrant-serve-sbatch.sh" >&2
    exit 1
fi

QDRANT_HOST=$(cat "$QDRANT_ENDPOINT_FILE")

echo "============================================"
echo "Job ID   : $SLURM_JOB_ID"
echo "Node     : $(hostname)"
echo "SIF      : $EMBEDDINGS_SIF"
echo "Port     : $INDEX_PORT"
echo "Qdrant   : $QDRANT_HOST"
echo "============================================"

# Clean up endpoint file on exit.
trap 'rm -f "$INDEX_ENDPOINT_FILE"' EXIT

# Fail fast if port is already in use on this node
if ss -tlnp 2>/dev/null | grep -q ":${INDEX_PORT} "; then
    echo "Error: port ${INDEX_PORT} is already in use on $(hostname)." >&2
    exit 1
fi

# Start index-server inside Singularity (no --rocm needed — CPU only).
# Reuses embeddings-api.sif which already has flask + qdrant-client.
# bash -c ensures LD_LIBRARY_PATH is exported inside the container.
singularity exec \
    --bind "$PROJECT_ROOT:/workspace" \
    "$EMBEDDINGS_SIF" \
    bash -c "
        export LD_LIBRARY_PATH=/usr/local/lib
        python /workspace/7-index/index_server.py \
            --qdrant-host ${QDRANT_HOST} \
            --port ${INDEX_PORT}
    " &
INDEX_PID=$!

echo "Index server PID: $INDEX_PID"

# Health-check loop: poll /health until 200 OK or timeout
echo "Waiting for index-server to become ready (timeout ${HEALTH_TIMEOUT}s)..."
ELAPSED=0
until curl -sf "http://localhost:${INDEX_PORT}/health" > /dev/null 2>&1; do
    if [ "$ELAPSED" -ge "$HEALTH_TIMEOUT" ]; then
        echo "Error: index-server did not become ready within ${HEALTH_TIMEOUT}s on $(hostname):${INDEX_PORT}" >&2
        exit 1
    fi
    sleep 2
    ELAPSED=$((ELAPSED + 2))
done

echo "Index server is ready after ${ELAPSED}s."

# Write endpoint file atomically
TMPFILE=$(mktemp "${INDEX_ENDPOINT_FILE}.XXXXXX")
echo "$(hostname):${INDEX_PORT}" > "$TMPFILE"
mv "$TMPFILE" "$INDEX_ENDPOINT_FILE"

echo "Endpoint written: $(cat "$INDEX_ENDPOINT_FILE")"

# Keep the job alive until wall time or the index-server process exits
wait "$INDEX_PID"
