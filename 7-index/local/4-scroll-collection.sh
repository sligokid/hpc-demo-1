#!/usr/bin/env bash
# Show sentiment_label and sentiment_score for all indexed videos.
# Prerequisite: Qdrant running (script 1).
set -euo pipefail

QDRANT_HOST="${QDRANT_HOST:-http://localhost:6333}"

curl -sf -X POST "$QDRANT_HOST/collections/video_metadata/points/scroll" \
  -H "Content-Type: application/json" \
  -d '{"limit": 100, "with_payload": true, "with_vector": false}' \
  | jq -r '.result.points[] | .payload | "\(.sentiment_label // "n/a")  \(.sentiment_score // "n/a")  \(.video_id // .file // "?")"'
