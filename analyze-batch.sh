#!/bin/bash
# SLURM array job: run analyze.py across a directory of transcripts in parallel.
#
# Prerequisites:
#   1. ollama-serve.sh is running and has written the endpoint file
#   2. ollama-pull.sh has been run to cache the model
#
# Submit:
#   N=$(find transcripts/ -name "*.txt" | wc -l)
#   sbatch --array=0-$((N-1)) analyze-batch.sh <transcript-folder>
#
# Chain with the Ollama service job:
#   JID=$(sbatch --parsable ollama-serve.sh)
#   N=$(find transcripts/ -name "*.txt" | wc -l)
#   sbatch --dependency=after:$JID --array=0-$((N-1)) analyze-batch.sh <transcript-folder>

#SBATCH --job-name=analyze-batch
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=01:00:00
#SBATCH --output=logs/%A_%a.out
#SBATCH --account=project_465003209
#SBATCH --partition=small-g

set -euo pipefail

# --- Configuration ---
#MODEL=${MODEL:-llama3.1:8b}
MODEL=${MODEL:-llama3}
TRANSCRIPT_DIR=${1:?Usage: sbatch analyze-batch.sh <transcript-folder>}
SCRATCH=/scratch/project_465003209/mcgowank
ENDPOINT_FILE=$SCRATCH/ollama.endpoint
#WHISPER_SIF=${WHISPER_SIF:-$SCRATCH/whisper-hpc.sif}
WHISPER_SIF=${WHISPER_SIF:-$SCRATCH/hpc-demo-1/whisper-hpc.sif}
# ---------------------

mkdir -p logs metadata

# Fail fast if the Ollama service is not running
if [ ! -f "$ENDPOINT_FILE" ]; then
    echo "Error: endpoint file not found at $ENDPOINT_FILE" >&2
    echo "Start the Ollama service first: sbatch ollama-serve.sh" >&2
    exit 1
fi

OLLAMA_HOST=$(cat "$ENDPOINT_FILE")

# Map array task ID to a transcript file
mapfile -t TRANSCRIPTS < <(find "$TRANSCRIPT_DIR" -maxdepth 1 -name "*.txt" | sort)

if [ ${#TRANSCRIPTS[@]} -eq 0 ]; then
    echo "Error: no .txt files found in $TRANSCRIPT_DIR/" >&2
    exit 1
fi

# Tasks beyond the file count exit cleanly — expected when array limit > N files
if [ "$SLURM_ARRAY_TASK_ID" -ge "${#TRANSCRIPTS[@]}" ]; then
    exit 0
fi

TRANSCRIPT=${TRANSCRIPTS[$SLURM_ARRAY_TASK_ID]}
BASENAME=$(basename "$TRANSCRIPT" .txt)
OUTPUT=metadata/${BASENAME}.json

echo "============================================"
echo "Job ID    : $SLURM_JOB_ID  Array task: $SLURM_ARRAY_TASK_ID"
echo "Transcript: $TRANSCRIPT"
echo "Output    : $OUTPUT"
echo "Endpoint  : $OLLAMA_HOST"
echo "Model     : $MODEL"
echo "============================================"

singularity exec \
    --bind "$PWD:/workspace" \
    "$WHISPER_SIF" \
    python /workspace/analyze.py \
        --transcript "/workspace/$TRANSCRIPT" \
        --model "$MODEL" \
        --ollama-host "$OLLAMA_HOST" \
    > "$OUTPUT"

echo "Written: $OUTPUT"
