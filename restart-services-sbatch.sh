#!/bin/bash
# Restart the five persistent services every 12 hours.
# Cancels the current service jobs by name, then resubmits them.
#
# Submit once from the project root to start the cycle:
#   sbatch restart-services.sh

#SBATCH --job-name=A-restart
#SBATCH --partition=small
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:15:00
#SBATCH --output=logs/restart-slurm-%j.out
#SBATCH --error=logs/restart-slurm-%j.err

set -euo pipefail

PROJECT_ROOT="$(cd "$SLURM_SUBMIT_DIR" && pwd)"

# Load site config (.env — never committed)
[ -f "$PROJECT_ROOT/.env" ] && source "$PROJECT_ROOT/.env"

mkdir -p "$PROJECT_ROOT/logs"

echo "============================================"
echo "Job ID  : $SLURM_JOB_ID"
echo "Started : $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "============================================"

# Resubmit this job every 12 hours.
trap 'sbatch --account="${HPC_ACCOUNT:?}" --begin=now+12hours "$SLURM_SUBMIT_DIR/restart-services-sbatch.sh" || echo "WARNING: D-restart resubmit failed"' EXIT

# Cancel services by name — safe to run inside a SLURM job (does not cancel this job).
echo "Cancelling service jobs..."
for job_name in B-ollama C-sync D-qdrant E-embed Z-poll; do
    scancel --name="$job_name" --user="$USER" 2>/dev/null || true
done

echo "Waiting 2 minutes for services to die..."
sleep 120

echo "Submitting B-ollama..."
OLLAMA_JID=$(sbatch --parsable --account="${HPC_ACCOUNT:?}" "$PROJECT_ROOT/3-analyze/hpc/2-ollama-serve-sbatch.sh")
echo "  Job ID: $OLLAMA_JID"
echo "Waiting 2 minutes for B-ollama to start..."
sleep 120

echo "Submitting C-sync..."
sbatch --account="${HPC_ACCOUNT:?}" "$PROJECT_ROOT/4-file-sync/hpc/sync-sbatch.sh"

echo "Submitting D-qdrant..."
QDRANT_JID=$(sbatch --parsable --account="${HPC_ACCOUNT:?}" "$PROJECT_ROOT/5-embed/hpc/qdrant-serve-sbatch.sh")
echo "  Job ID: $QDRANT_JID"
echo "Waiting 2 minutes for D-qdrant to write endpoint file..."
sleep 120

echo "Submitting E-embed..."
EMBED_JID=$(sbatch --parsable --account="${HPC_ACCOUNT:?}" "$PROJECT_ROOT/5-embed/hpc/embeddings-serve-sbatch.sh")
echo "  Job ID: $EMBED_JID"

# Z-poll must not start until Ollama, Qdrant, and the embed server are all running.
echo "Submitting Z-poll (depends on B-ollama:$OLLAMA_JID, D-qdrant:$QDRANT_JID, E-embed:$EMBED_JID)..."
sbatch --account="${HPC_ACCOUNT:?}" --dependency=after:${OLLAMA_JID}:${QDRANT_JID}:${EMBED_JID} "$PROJECT_ROOT/pipeline-hpc-poll.sh"

echo "Done. Next restart scheduled in 12 hours."
