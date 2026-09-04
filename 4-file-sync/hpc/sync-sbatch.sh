#!/bin/bash
# SLURM job: Poll Google Drive and sync files to/from HPC scratch.
#
# Runs one sync cycle then resubmits itself to create a 5-minute polling loop.
# No crontab required — the chain is started once and continues indefinitely.
#
# Submit from the project root:
#   sbatch 4-file-sync/hpc/sync-sbatch.sh
#
# Stop the chain:
#   scancel <jobid>
#
# Monitor:
#   squeue -u $USER
#   tail -f logs/sync-<timestamp>.out
#

#SBATCH --job-name=whisper-sync
#SBATCH --partition=small
#SBATCH --account=project_465003209
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:10:00
#SBATCH --output=logs/sync-slurm-%j.out
#SBATCH --error=logs/sync-slurm-%j.err

SIF=/scratch/project_465003209/mcgowank/whisper-sync.sif

# Always submitted from the project root — SLURM_SUBMIT_DIR is the project root.
PROJECT_ROOT="$(cd "$SLURM_SUBMIT_DIR" && pwd)"
SYNC_SCRIPT="$PROJECT_ROOT/4-file-sync/hpc/sync-sbatch.sh"

mkdir -p "$PROJECT_ROOT/sync/input" "$PROJECT_ROOT/sync/output" "$PROJECT_ROOT/logs"

echo "============================================"
echo "Job ID   : $SLURM_JOB_ID"
echo "Node     : $(hostname)"
echo "Started  : $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Root     : $PROJECT_ROOT"
echo "============================================"

# Resubmit this job on EXIT regardless of success or failure,
# so the polling chain is never permanently broken by a single error.
trap 'sbatch --begin=now+5minutes "$SYNC_SCRIPT" || echo "WARNING: resubmit failed — chain stopped"' EXIT

# rclone config lives on the host at ~/.config/rclone/rclone.conf.
# The rclone/rclone image expects it at /config/rclone/rclone.conf inside the container.
singularity exec \
    --bind "$PROJECT_ROOT:/workspace" \
    --bind "$HOME/.config/rclone:/config/rclone" \
    "$SIF" \
    bash -c "
        export WORKSPACE=/workspace
        export RCLONE_REMOTE=gdrive
        export DRIVE_INPUT=gdrive:whisper-sync/input
        export DRIVE_OUTPUT=gdrive:whisper-sync/output
        /usr/local/bin/sync.sh
    "
