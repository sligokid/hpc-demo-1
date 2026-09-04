#!/bin/bash
# SLURM scheduler: check for new audio files every 10 minutes and submit the pipeline.
#
# Runs pipeline-hpc-submit.sh on each cycle. 
#   - If new files are found a pipeline array job is submitted automatically. If no files are pending, does nothing.
#
# Submit once from the project root to start the polling loop:
#   sbatch pipeline-hpc-poll.sh
#
# Stop the loop:
#   scancel <jobid>
#
# Monitor:
#   squeue -u $USER
#   tail -f logs/poll-slurm-<jobid>.out

#SBATCH --job-name=pipeline-poll
#SBATCH --partition=small
#SBATCH --account=project_465003209
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:05:00
#SBATCH --output=logs/poll-slurm-%j.out
#SBATCH --error=logs/poll-slurm-%j.err

set -euo pipefail

PROJECT_ROOT="$(cd "$SLURM_SUBMIT_DIR" && pwd)"

mkdir -p "$PROJECT_ROOT/logs"

echo "============================================"
echo "Job ID  : $SLURM_JOB_ID"
echo "Node    : $(hostname)"
echo "Started : $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "============================================"

# Resubmit this scheduler every 10 minutes regardless of outcome.
trap 'sbatch --begin=now+10minutes "$SLURM_SUBMIT_DIR/pipeline-hpc-poll.sh" || echo "WARNING: resubmit failed — polling stopped"' EXIT

# Check for pending files and submit pipeline array job if any are found.
"$PROJECT_ROOT/pipeline-hpc-submit.sh"
