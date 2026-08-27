#!/bin/bash
# Interactive srun wrapper: analyze a single transcript using the running Ollama service.
#
# Usage:
#   ./analyze-on-gpu.sh <transcript-file>
#
# Example:
#   ./analyze-on-gpu.sh transcripts/foo.txt

set -euo pipefail

TRANSCRIPT=${1:?Usage: analyze-on-gpu.sh <transcript-file>}

SCRATCH=/scratch/project_465003209/mcgowank
ENDPOINT_FILE=$SCRATCH/ollama.endpoint
WHISPER_SIF=${WHISPER_SIF:-$SCRATCH/whisper-hpc.sif}
MODEL=${MODEL:-llama3.1:8b}

if [ ! -f "$ENDPOINT_FILE" ]; then
    echo "Error: endpoint file not found at $ENDPOINT_FILE" >&2
    echo "Start the Ollama service first: sbatch ollama-serve.sh" >&2
    exit 1
fi

OLLAMA_HOST=$(cat "$ENDPOINT_FILE")

echo "Transcript : $TRANSCRIPT"
echo "Endpoint   : $OLLAMA_HOST"
echo "Model      : $MODEL"

srun \
    --account project_465003209 \
    --partition small-g \
    --time 00:30:00 \
    --ntasks 1 \
    --cpus-per-task 1 \
    --mem 4G \
    singularity exec \
        --bind "$PWD:/workspace" \
        "$WHISPER_SIF" \
        python /workspace/analyze.py \
            --transcript "/workspace/$TRANSCRIPT" \
            --model "$MODEL" \
            --ollama-host "$OLLAMA_HOST"
