#!/bin/bash
# Scan sync/output/ for pending *.teleprompter.md files, build a manifest, and submit
# a SLURM array job to run tts.py on each one.
#
# Usage:
#   ./12-tts/hpc/tts-hpc-submit.sh

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"
PROJECT_ROOT="$(cd "../.." && pwd)"

SCRATCH=/scratch/project_465003359/mcgowank
OLLAMA_ENDPOINT_FILE=$SCRATCH/ollama.endpoint
TTS_MODEL=lfm3-audio

# --- Verify Ollama is reachable and model is available ---
[ -f "$OLLAMA_ENDPOINT_FILE" ] || { echo "Error: Ollama endpoint not found at $OLLAMA_ENDPOINT_FILE" >&2; exit 1; }
OLLAMA_HOST=$(cat "$OLLAMA_ENDPOINT_FILE")

echo "Ollama host : $OLLAMA_HOST"

if ! curl -sf "http://$OLLAMA_HOST/api/tags" | grep -q "\"$TTS_MODEL\""; then
    echo "Pulling model '$TTS_MODEL' into Ollama..."
    curl -sf -X POST "http://$OLLAMA_HOST/api/pull" \
        -d "{\"name\":\"$TTS_MODEL\"}" | tail -1
fi

mkdir -p "$PROJECT_ROOT/logs"
MANIFEST="$PROJECT_ROOT/logs/tts-manifest-$(date +%Y%m%d-%H%M%S).txt"

# Scan sync/output/ for pending *.teleprompter.md — skip if WAV already exists
for dir in "$PROJECT_ROOT/sync/output/"/*/; do
    [ -d "$dir" ] || continue
    for f in "$dir"*.teleprompter.md; do
        [ -f "$f" ] || continue
        LANG=$(basename "$dir")
        STEM=$(basename "$f" .teleprompter.md)
        [ -f "$PROJECT_ROOT/sync/output/$LANG/$STEM.teleprompter.wav" ] && continue
        # Write path relative to project root (for /workspace/ mapping in singularity)
        echo "sync/output/$LANG/$STEM.teleprompter.md"
    done
done | sort > "$MANIFEST"

N=$(wc -l < "$MANIFEST")
if [ "$N" -eq 0 ]; then
    echo "No pending teleprompter files found."
    rm "$MANIFEST"
    exit 0
fi

echo "Pending files : $N"
echo "Manifest      : $MANIFEST"
cat "$MANIFEST"
echo ""

JID=$(sbatch --array=0-$((N - 1)) tts-sbatch.sh "$MANIFEST" --parsable)
echo "Submitted array job $JID ($N tasks)"
echo "Monitor: squeue -u \$USER"
echo "Logs   : $PROJECT_ROOT/logs/${JID}_*.out"
