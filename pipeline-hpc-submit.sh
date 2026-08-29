#!/bin/bash
# Generate a manifest of pending audio files and submit a SLURM array job.
# One array task per file — all run in parallel.
#
# Usage:
#   ./pipeline-hpc-submit.sh
#   ./pipeline-hpc-submit.sh --lang en
#
# Chain with Ollama service (start service, then submit pipeline when ready):
#   JID=$(sbatch --parsable 3-analyze/hpc/2-ollama-serve-sbatch.sh)
#   ./pipeline-hpc-submit.sh --dependency after:$JID

set -euo pipefail

cd "$(dirname "$0")"

DEPENDENCY=""
LANG_FILTER=""
INBOX=$(grep '^inbox:' pipeline.yaml | awk '{print $2}')

while [[ $# -gt 0 ]]; do
    case $1 in
        --dependency) DEPENDENCY="--dependency $2"; shift 2 ;;
        --lang)       LANG_FILTER="$2"; shift 2 ;;
        *) echo "Unknown arg: $1" >&2; exit 1 ;;
    esac
done

# Build manifest in the project dir (shared filesystem — readable by compute nodes)
mkdir -p logs
MANIFEST="$PWD/logs/pipeline-manifest-$(date +%Y%m%d-%H%M%S).txt"

if [ -n "$LANG_FILTER" ]; then
    SEARCH_DIRS=("$INBOX/$LANG_FILTER")
else
    SEARCH_DIRS=("$INBOX"/*)
fi

for dir in "${SEARCH_DIRS[@]}"; do
    [ -d "$dir" ] || continue
    for f in "$dir"/*.{mp3,mp4,wav,flac,m4a,ogg}; do
        [ -f "$f" ] || continue
        [ -f "$f.done" ] && continue
        echo "$PWD/$f"
    done
done > "$MANIFEST"

N=$(wc -l < "$MANIFEST")
if [ "$N" -eq 0 ]; then
    echo "No pending files found."
    rm "$MANIFEST"
    exit 0
fi

echo "Pending files : $N"
echo "Manifest      : $MANIFEST"
cat "$MANIFEST"
echo ""

# shellcheck disable=SC2086
JID=$(sbatch \
    --array=0-$((N - 1)) \
    $DEPENDENCY \
    pipeline-hpc-sbatch.sh "$MANIFEST" \
    --parsable)

echo "Submitted array job $JID ($N tasks)"
echo "Monitor: squeue -u \$USER"
echo "Logs   : logs/${JID}_*.out"
