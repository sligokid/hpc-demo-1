#!/bin/bash
#SBATCH --job-name=G-teleprompter
#SBATCH --partition=small
#SBATCH --account=project_465003359
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:10:00
#SBATCH --output=logs/teleprompter-submit-%j.out

set -euo pipefail

# cd to this script's dir so sbatch sets SLURM_SUBMIT_DIR=11-sop/hpc/ in the array job
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

JID=$(sbatch --array=0-$((N - 1)) ./teleprompter-sbatch.sh "$MANIFEST" --parsable)
echo "Submitted array job $JID ($N tasks)"
