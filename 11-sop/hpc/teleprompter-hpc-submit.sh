#!/bin/bash
# Scan sync/input/ for pending *.sop.md files, build a manifest, and submit
# a SLURM array job to run teleprompter.py on each one.
#
# Usage:
#   ./11-sop/hpc/teleprompter-hpc-submit.sh

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"
PROJECT_ROOT="$(cd "../.." && pwd)"

mkdir -p "$PROJECT_ROOT/logs"
MANIFEST="$PROJECT_ROOT/logs/teleprompter-manifest-$(date +%Y%m%d-%H%M%S).txt"

# Scan sync/input/ for pending *.sop.md — skip if output already exists
for dir in "$PROJECT_ROOT/sync/input/"/*/; do
    [ -d "$dir" ] || continue
    for f in "$dir"*.sop.md; do
        [ -f "$f" ] || continue
        LANG=$(basename "$dir")
        STEM=$(basename "$f" .sop.md)
        [ -f "$PROJECT_ROOT/sync/output/$LANG/$STEM.teleprompter.md" ] && continue
        # Write path relative to project root (for /workspace/ mapping in singularity)
        echo "sync/input/$LANG/$STEM.sop.md"
    done
done | sort > "$MANIFEST"

N=$(wc -l < "$MANIFEST")
if [ "$N" -eq 0 ]; then
    echo "No pending SOP files found."
    rm "$MANIFEST"
    exit 0
fi

echo "Pending SOPs : $N"
echo "Manifest     : $MANIFEST"
cat "$MANIFEST"
echo ""

JID=$(sbatch --array=0-$((N - 1)) teleprompter-sbatch.sh "$MANIFEST" --parsable)
echo "Submitted array job $JID ($N tasks)"
echo "Monitor: squeue -u \$USER"
echo "Logs   : $PROJECT_ROOT/logs/${JID}_*.out"
