#!/bin/bash
#SBATCH --job-name=H-tts
#SBATCH --partition=small
#SBATCH --account=project_465003359
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:30:00
#SBATCH --output=logs/%A_%a.out
#SBATCH --no-requeue

set -euo pipefail

MANIFEST=${1:?Usage: sbatch --array=0-N 12-tts/hpc/tts-sbatch.sh <manifest-file>}
SCRATCH=/scratch/project_465003359/mcgowank
SIF=$SCRATCH/tts-tools.sif
OLLAMA_ENDPOINT_FILE=$SCRATCH/ollama.endpoint
# SLURM_SUBMIT_DIR = 12-tts/hpc/ (set by tts-hpc-submit.sh calling sbatch from its own dir)
PROJECT_ROOT="$(cd "$SLURM_SUBMIT_DIR/../.." && pwd)"

mkdir -p "$PROJECT_ROOT/logs"

[ -f "$OLLAMA_ENDPOINT_FILE" ] || { echo "Error: Ollama endpoint not found at $OLLAMA_ENDPOINT_FILE" >&2; exit 1; }
OLLAMA_HOST=$(cat "$OLLAMA_ENDPOINT_FILE")

mapfile -t FILES < "$MANIFEST"
[ "$SLURM_ARRAY_TASK_ID" -ge "${#FILES[@]}" ] && exit 0  # array overrun

TELEPROMPTER_FILE=${FILES[$SLURM_ARRAY_TASK_ID]}
LANG=$(basename "$(dirname "$TELEPROMPTER_FILE")")
STEM=$(basename "$TELEPROMPTER_FILE" .teleprompter.md)

echo "============================"
echo "Job   : $SLURM_JOB_ID  Task: $SLURM_ARRAY_TASK_ID"
echo "File  : $TELEPROMPTER_FILE"
echo "Ollama: $OLLAMA_HOST"
echo "============================"

singularity exec \
    --bind "$PROJECT_ROOT:/workspace" \
    "$SIF" \
    bash -c "
export LD_LIBRARY_PATH=/opt/rocm/lib:/opt/rocm/lib64:/usr/local/lib
python /workspace/12-tts/tts.py \
    --input       \"/workspace/$TELEPROMPTER_FILE\" \
    --output      \"/workspace/sync/output/$LANG/$STEM\" \
    --ollama-host \"$OLLAMA_HOST\" \
    --model       lfm3-audio \
    --voice       male
"
