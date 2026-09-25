#!/usr/bin/env bash
# Generate the knowledge graph and a personalised playlist from the video_metadata
# Qdrant collection.
#
# Prerequisites: Qdrant running and video_metadata collection populated.
#
# Usage:
#   ./6-graph/create-playlist-graph.sh
#   ./6-graph/create-playlist-graph.sh --user engineer@org.com --top-n 10
#   ./6-graph/create-playlist-graph.sh --user operative@org.com --sentiment positive
#   ./6-graph/create-playlist-graph.sh --no-personalise --user engineer@org.com
#   ./6-graph/create-playlist-graph.sh --qdrant-host localhost:6333 --user manager@org.com
#
# Flags (all optional):
#   --user USER             User profile to generate playlist for (default: engineer@org.com)
#   --top-n N               Number of playlist results (default: 10)
#   --sentiment LABEL       Filter playlist by sentiment: positive | neutral | negative
#   --no-personalise        Disable personalisation (EU AI Act opt-out)
#   --qdrant-host HOST:PORT Qdrant address (default: localhost:6333)
#   --output PATH           graph.json output path (default: sync/output/graph.json)

set -euo pipefail

cd "$(dirname "$0")/.."
source venv/bin/activate

# --- defaults ---
USER_ARG="engineer@org.com"
TOP_N="10"
SENTIMENT=""
NO_PERSONALISE=""
QDRANT_HOST="localhost:6333"
GRAPH_OUTPUT="sync/output/graph.json"

# --- parse args ---
while [[ $# -gt 0 ]]; do
  case "$1" in
    --user)           USER_ARG="$2";      shift 2 ;;
    --top-n)          TOP_N="$2";         shift 2 ;;
    --sentiment)      SENTIMENT="$2";     shift 2 ;;
    --no-personalise) NO_PERSONALISE="1"; shift   ;;
    --qdrant-host)    QDRANT_HOST="$2";   shift 2 ;;
    --output)         GRAPH_OUTPUT="$2";  shift 2 ;;
    *) echo "Unknown flag: $1" >&2; exit 1 ;;
  esac
done

GRAPH_HTML="${GRAPH_OUTPUT%.json}.html"
PLAYLIST_OUTPUT="sync/output/playlist-${USER_ARG}.json"

echo "=== SLICK+ Knowledge Graph & Playlist ==="
echo "  Qdrant     : $QDRANT_HOST"
echo "  User       : $USER_ARG"
echo "  Top-N      : $TOP_N"
echo "  Sentiment  : ${SENTIMENT:-any}"
echo "  Personalise: $([ -n "$NO_PERSONALISE" ] && echo no || echo yes)"
echo ""

# --- graph ---
echo "--- graph.py ---"
python 6-graph/graph.py \
  --qdrant-host "$QDRANT_HOST" \
  --output "$GRAPH_OUTPUT"

echo ""

# --- playlist ---
echo "--- playlist.py ---"

PLAYLIST_ARGS=(
  --user        "$USER_ARG"
  --top-n       "$TOP_N"
  --qdrant-host "$QDRANT_HOST"
)
[ -n "$SENTIMENT" ]      && PLAYLIST_ARGS+=(--sentiment "$SENTIMENT")
[ -n "$NO_PERSONALISE" ] && PLAYLIST_ARGS+=(--no-personalise)

mkdir -p "$(dirname "$PLAYLIST_OUTPUT")"
python 6-graph/playlist.py "${PLAYLIST_ARGS[@]}" | tee "$PLAYLIST_OUTPUT"

echo ""
echo "=== Done ==="
echo "  Graph JSON  : $GRAPH_OUTPUT"
echo "  Graph HTML  : $GRAPH_HTML"
echo "  Playlist    : $PLAYLIST_OUTPUT"
