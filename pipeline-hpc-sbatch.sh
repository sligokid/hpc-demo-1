#!/bin/bash
# SLURM batch job: run the full pipeline (infer -> analyze) on HPC.
#
# Prerequisites:
#   1. Ollama service is running and has written the endpoint file:
#        JID=$(sbatch --parsable 3-analyze/hpc/2-ollama-serve-sbatch.sh)
#        sbatch --dependency=after:$JID pipeline-hpc-sbatch.sh
#   2. Ollama model has been pulled (3-analyze/hpc/3-ollama-pull-llama3.sh)
#
# Submit:
#   sbatch pipeline-hpc-sbatch.sh
#   sbatch pipeline-hpc-sbatch.sh --lang en

#SBATCH --job-name=pipeline
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --gres=gpu:1
#SBATCH --output=logs/%j.out
#SBATCH --account=project_465003209
#SBATCH --partition=small-g

set -euo pipefail

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

echo "Project root : $PROJECT_ROOT"
echo "Ollama host  : $OLLAMA_HOST"

singularity exec \
    --rocm \
    --bind "$PROJECT_ROOT:/workspace" \
    "$SIF" \
    bash -c "
export LD_LIBRARY_PATH=/opt/rocm/lib:/opt/rocm/lib64:/usr/local/lib
export MIOPEN_DISABLE_CACHE=1
python /workspace/pipeline.py \
    --config /workspace/pipeline.yaml \
    --ollama-host \"$OLLAMA_HOST\" \
    $*
"
