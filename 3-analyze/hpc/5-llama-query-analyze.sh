#!/bin/bash
# Pipe a transcript into analyze.py via the running Ollama HPC service.
#
# Usage:
#   ./5-llama-query-analyze-stdin.sh

REPO_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
SCRATCH=/scratch/project_465003209/mcgowank
ENDPOINT_FILE=$SCRATCH/ollama.endpoint
WHISPER_SIF=${WHISPER_SIF:-$SCRATCH/whisper-hpc.sif}
MODEL=${MODEL:-llama3}

if [ ! -f "$ENDPOINT_FILE" ]; then
    echo "Error: endpoint file not found at $ENDPOINT_FILE" >&2
    echo "Start the Ollama service first: sbatch 2-ollama-serve-sbatch.sh" >&2
    exit 1
fi

OLLAMA_HOST=$(cat "$ENDPOINT_FILE")

singularity exec \
    --bind "$REPO_ROOT:/workspace" \
    "$WHISPER_SIF" \
    python /workspace/3-analyze/analyze.py \
        --transcript /workspace/results/infer-on-gpu.sh.txt \
        --model "$MODEL" \
        --ollama-host "$OLLAMA_HOST"
