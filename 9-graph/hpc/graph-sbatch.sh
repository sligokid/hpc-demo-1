#!/bin/bash
# Build the knowledge graph and personalised playlist on LUMI.
# Reads video_metadata from the running Qdrant service and writes graph.json,
# graph.html and a per-user playlist JSON to sync/output/.
#
# Prerequisites:
#   E-qdrant service is running and has written the endpoint file.
#
# Submit from the project root:
#   sbatch 9-graph/hpc/graph-sbatch.sh
#   sbatch 9-graph/hpc/graph-sbatch.sh --user operative@org.com --top-n 5
#   sbatch 9-graph/hpc/graph-sbatch.sh --user engineer@org.com --sentiment positive
#   sbatch 9-graph/hpc/graph-sbatch.sh --no-personalise --user manager@org.com
#
# Flags (all optional, must come after the script name):
#   --user USER         User profile (default: engineer@org.com)
#   --top-n N           Playlist results (default: 10)
#   --sentiment LABEL   Filter: positive | neutral | negative
#   --no-personalise    Disable personalisation (EU AI Act opt-out)
#   --output PATH       graph.json output path (default: sync/output/graph.json)

#SBATCH --job-name=G-graph
#SBATCH --partition=small
#SBATCH --account=project_465003359
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:30:00
#SBATCH --output=logs/graph-slurm-%j.out
#SBATCH --error=logs/graph-slurm-%j.err

set -euo pipefail

# --- Configuration ---
SCRATCH=${SCRATCH:-/scratch/project_465003359/mcgowank}
SIF=${SIF:-$SCRATCH/embeddings-api.sif}
QDRANT_ENDPOINT_FILE=$SCRATCH/qdrant.endpoint
# ---------------------

# Resolve project root whether submitted from the project root or 9-graph/hpc/
if [ -f "$SLURM_SUBMIT_DIR/pipeline.yaml" ]; then
    PROJECT_ROOT="$(cd "$SLURM_SUBMIT_DIR" && pwd)"
else
    PROJECT_ROOT="$(cd "$SLURM_SUBMIT_DIR/../.." && pwd)"
fi

mkdir -p "$PROJECT_ROOT/logs" "$PROJECT_ROOT/sync/output"

# --- defaults ---
USER_ARG="engineer@org.com"
TOP_N="10"
SENTIMENT=""
NO_PERSONALISE=""
GRAPH_OUTPUT="sync/output/graph.json"

# --- parse args passed after the script name to sbatch ---
while [[ $# -gt 0 ]]; do
  case "$1" in
    --user)           USER_ARG="$2";      shift 2 ;;
    --top-n)          TOP_N="$2";         shift 2 ;;
    --sentiment)      SENTIMENT="$2";     shift 2 ;;
    --no-personalise) NO_PERSONALISE="1"; shift   ;;
    --output)         GRAPH_OUTPUT="$2";  shift 2 ;;
    *) echo "Unknown flag: $1" >&2; exit 1 ;;
  esac
done

PLAYLIST_OUTPUT="sync/output/playlist-${USER_ARG}.json"

echo "============================================"
echo "Job ID     : $SLURM_JOB_ID"
echo "Node       : $(hostname)"
echo "SIF        : $SIF"
echo "User       : $USER_ARG"
echo "Top-N      : $TOP_N"
echo "Sentiment  : ${SENTIMENT:-any}"
echo "Personalise: $([ -n "$NO_PERSONALISE" ] && echo no || echo yes)"
echo "Graph out  : $GRAPH_OUTPUT"
echo "Playlist   : $PLAYLIST_OUTPUT"
echo "============================================"

# --- Qdrant endpoint ---
if [ ! -f "$QDRANT_ENDPOINT_FILE" ]; then
    echo "Error: Qdrant endpoint file not found at $QDRANT_ENDPOINT_FILE" >&2
    echo "Start the Qdrant service first: sbatch 7-index/hpc/1-qdrant-serve-sbatch.sh" >&2
    exit 1
fi
QDRANT_HOST=$(cat "$QDRANT_ENDPOINT_FILE")
echo "Qdrant     : $QDRANT_HOST"
echo ""

# --- graph.py ---
echo "--- graph.py ---"
singularity exec \
    --bind "$PROJECT_ROOT:/workspace" \
    "$SIF" \
    bash -c "
export LD_LIBRARY_PATH=/opt/rocm/lib:/opt/rocm/lib64:/usr/local/lib
python /workspace/9-graph/graph.py \
    --qdrant-host \"$QDRANT_HOST\" \
    --output \"/workspace/$GRAPH_OUTPUT\"
"

echo ""

# --- playlist.py ---
echo "--- playlist.py ---"

PLAYLIST_ARGS=(
    --user        "$USER_ARG"
    --top-n       "$TOP_N"
    --qdrant-host "$QDRANT_HOST"
)
[ -n "$SENTIMENT" ]      && PLAYLIST_ARGS+=(--sentiment "$SENTIMENT")
[ -n "$NO_PERSONALISE" ] && PLAYLIST_ARGS+=(--no-personalise)

singularity exec \
    --bind "$PROJECT_ROOT:/workspace" \
    "$SIF" \
    bash -c "
export LD_LIBRARY_PATH=/opt/rocm/lib:/opt/rocm/lib64:/usr/local/lib
python /workspace/9-graph/playlist.py ${PLAYLIST_ARGS[*]}
" | tee "$PROJECT_ROOT/$PLAYLIST_OUTPUT"

echo ""
echo "=== Done ==="
echo "  Graph JSON  : $PROJECT_ROOT/$GRAPH_OUTPUT"
echo "  Graph HTML  : ${PROJECT_ROOT}/${GRAPH_OUTPUT%.json}.html"
echo "  Playlist    : $PROJECT_ROOT/$PLAYLIST_OUTPUT"
