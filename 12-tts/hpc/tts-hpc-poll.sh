#!/bin/bash
# SLURM scheduler: check for new teleprompter files every 10 minutes and submit TTS.
#
# Submit once from the project root to start the polling loop:
#   sbatch 12-tts/hpc/tts-hpc-poll.sh
#
# Stop the loop:
#   scancel --name=H-tts --user=$USER

#SBATCH --job-name=H-tts
#SBATCH --partition=small
#SBATCH --account=project_465003359
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:15:00
#SBATCH --output=logs/tts-poll-%j.out
#SBATCH --error=logs/tts-poll-%j.err

set -euo pipefail

PROJECT_ROOT="$(cd "$SLURM_SUBMIT_DIR" && pwd)"

mkdir -p "$PROJECT_ROOT/logs"

echo "============================================"
echo "Job ID  : $SLURM_JOB_ID"
echo "Node    : $(hostname)"
echo "Started : $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "============================================"

# Resubmit every 10 minutes regardless of outcome.
trap 'sbatch --begin=now+10minutes "$SLURM_SUBMIT_DIR/12-tts/hpc/tts-hpc-poll.sh" || echo "WARNING: resubmit failed — polling stopped"' EXIT

# Check for pending teleprompter files and submit array job if any are found.
bash "$PROJECT_ROOT/12-tts/hpc/tts-hpc-submit.sh"
