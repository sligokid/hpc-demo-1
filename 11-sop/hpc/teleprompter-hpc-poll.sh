#!/bin/bash
# SLURM scheduler: check for new SOP files every 10 minutes and submit the teleprompter.
#
# Submit once from the project root to start the polling loop:
#   sbatch 11-sop/hpc/teleprompter-hpc-poll.sh
#
# Stop the loop:
#   scancel --name=G-teleprompter --user=$USER

#SBATCH --job-name=G-teleprompter
#SBATCH --partition=small
#SBATCH --account=project_465003359
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:15:00
#SBATCH --output=logs/sop-poll-%j.out
#SBATCH --error=logs/sop-poll-%j.err

set -euo pipefail

PROJECT_ROOT="$(cd "$SLURM_SUBMIT_DIR" && pwd)"

mkdir -p "$PROJECT_ROOT/logs"

echo "============================================"
echo "Job ID  : $SLURM_JOB_ID"
echo "Node    : $(hostname)"
echo "Started : $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "============================================"

# Resubmit every 10 minutes regardless of outcome.
trap 'sbatch --begin=now+10minutes "$SLURM_SUBMIT_DIR/11-sop/hpc/teleprompter-hpc-poll.sh" || echo "WARNING: resubmit failed — polling stopped"' EXIT

# Check for pending SOP files and submit array job if any are found.
bash "$PROJECT_ROOT/11-sop/hpc/teleprompter-hpc-submit.sh"
