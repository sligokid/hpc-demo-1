#!/bin/bash
# SLURM array job: run the full pipeline (infer -> analyze) for each audio file in parallel.
# Each array task processes one file from the manifest.
#
# Do not submit this script directly — use pipeline-hpc-submit.sh which generates the manifest and sets --array correctly.
#
# Prerequisites:
#   1. Ollama service is running and has written the endpoint file
#   2. Ollama model has been pulled (3-analyze/hpc/3-ollama-pull-llama3.sh)

#SBATCH --job-name=pipeline
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --gres=gpu:1
#SBATCH --output=logs/%A_%a.out
#SBATCH --account=project_465003209
#SBATCH --partition=small-g

set -euo pipefail

MANIFEST=${1:?Usage: sbatch --array=0-N pipeline-hpc-sbatch.sh <manifest-file>}
SCRATCH=/scratch/project_465003209/mcgowank
SIF=$SCRATCH/whisper-hpc.sif
ENDPOINT_FILE=$SCRATCH/ollama.endpoint
PROJECT_ROOT="$(cd "$SLURM_SUBMIT_DIR" && pwd)"

mkdir -p "$PROJECT_ROOT/logs"

if [ ! -f "$ENDPOINT_FILE" ]; then
    echo "Error: Ollama endpoint file not found at $ENDPOINT_FILE" >&2
    echo "Start the Ollama service first: sbatch 3-analyze/hpc/2-ollama-serve-sbatch.sh" >&2
    exit 1
fi

OLLAMA_HOST=$(cat "$ENDPOINT_FILE")

# Pick this task's file from the manifest
mapfile -t FILES < "$MANIFEST"

if [ "$SLURM_ARRAY_TASK_ID" -ge "${#FILES[@]}" ]; then
    exit 0  # array overrun — clean exit
fi

AUDIO_FILE=${FILES[$SLURM_ARRAY_TASK_ID]}
# Manifest contains paths relative to project root — map straight into /workspace
AUDIO_CONTAINER="/workspace/$AUDIO_FILE"

echo "============================================"
echo "Job       : $SLURM_JOB_ID  Array task: $SLURM_ARRAY_TASK_ID"
echo "File      : $AUDIO_FILE"
echo "Endpoint  : $OLLAMA_HOST"
echo "============================================"

singularity exec \
    --rocm \
    --bind "$PROJECT_ROOT:/workspace" \
    "$SIF" \
    bash -c "
export LD_LIBRARY_PATH=/opt/rocm/lib:/opt/rocm/lib64:/usr/local/lib
export MIOPEN_DISABLE_CACHE=1
python /workspace/pipeline.py \
    --config /workspace/pipeline.yaml \
    --file \"$AUDIO_CONTAINER\" \
    --ollama-host \"$OLLAMA_HOST\"
"
