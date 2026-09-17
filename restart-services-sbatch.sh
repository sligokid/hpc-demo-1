#!/bin/bash
# Restart the three persistent services every 12 hours.
# Cancels the current service jobs by name, then resubmits them.
#
# Submit once from the project root to start the cycle:
#   sbatch restart-services.sh

#SBATCH --job-name=D-restart
#SBATCH --partition=small
#SBATCH --account=project_465003209
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:05:00
#SBATCH --output=logs/restart-slurm-%j.out
#SBATCH --error=logs/restart-slurm-%j.err

set -euo pipefail

PROJECT_ROOT="$(cd "$SLURM_SUBMIT_DIR" && pwd)"

mkdir -p "$PROJECT_ROOT/logs"

echo "============================================"
echo "Job ID  : $SLURM_JOB_ID"
echo "Started : $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "============================================"

# Resubmit this job every 12 hours.
trap 'sbatch --begin=now+12hours "$SLURM_SUBMIT_DIR/restart-services-sbatch.sh" || echo "WARNING: D-restart resubmit failed"' EXIT

# Cancel services by name — safe to run inside a SLURM job (does not cancel this job).
echo "Cancelling service jobs..."
for job_name in A-ollama B-sync C-poll; do
    scancel --name="$job_name" --user="$USER" 2>/dev/null || true
done

echo "Submitting A-ollama..."
sbatch "$PROJECT_ROOT/3-analyze/hpc/2-ollama-serve-sbatch.sh"
echo "Waiting 2 minutes for A-ollama to start..."
sleep 120

echo "Submitting B-sync..."
sbatch "$PROJECT_ROOT/4-file-sync/hpc/sync-sbatch.sh"

echo "Submitting C-poll..."
sbatch "$PROJECT_ROOT/pipeline-hpc-poll.sh"

echo "Done. Next restart scheduled in 12 hours."
