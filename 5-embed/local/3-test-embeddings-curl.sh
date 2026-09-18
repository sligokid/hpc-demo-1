#!/usr/bin/env bash
# Smoke-test the embed-server and Qdrant with plain curl.
# Prerequisites: Qdrant running (script 1), embed-server running (script 2).
# Run from the project root or from this directory.
set -euo pipefail

EMBED_HOST="${EMBED_HOST:-http://localhost:8765}"
QDRANT_HOST="${QDRANT_HOST:-http://localhost:6333}"
COLLECTION="video_chunks"

echo "=== 1. Health check ==="
curl -sf "$EMBED_HOST/health" | python3 -m json.tool

echo ""
echo "=== 2. Index sample transcript chunks via POST /embed ==="
curl -sf -X POST "$EMBED_HOST/embed" \
  -H "Content-Type: application/json" \
  -d '{
    "video_id": "en/curl-test",
    "file": "inbox/en/curl-test.mp3",
    "lang": "en",
    "chunks": [
      {"text": "Machine learning models learn patterns from data automatically.", "timestamp_start": 0.0,  "timestamp_end": 4.2},
      {"text": "Deep neural networks are used for image and speech recognition.", "timestamp_start": 4.2,  "timestamp_end": 8.7},
      {"text": "The training loop updates weights using gradient descent.",       "timestamp_start": 8.7,  "timestamp_end": 13.1}
    ]
  }' | python3 -m json.tool

echo ""
echo "=== 3. Verify chunks are stored (Qdrant scroll) ==="
curl -sf -X POST "$QDRANT_HOST/collections/$COLLECTION/points/scroll" \
  -H "Content-Type: application/json" \
  -d '{
    "filter": {
      "must": [{"key": "video_id", "match": {"value": "en/curl-test"}}]
    },
    "limit": 10,
    "with_payload": true,
    "with_vector": false
  }' | python3 -m json.tool

echo ""
echo "=== 4. Semantic query: retrieve stored vector then search with it ==="
# Grab the vector of the first indexed point so we can run a nearest-neighbour
# search — this simulates asking "what chunks are about machine learning?"
# In production you would call the embed-server with the query text instead.
# Note: The query vector is pulled from the first stored point as a proxy. 
# For true query-by-text, the embed server would need a /search endpoint (or you'd call 
# Qdrant with a pre-computed embedding). 

POINT_ID=$(curl -sf -X POST "$QDRANT_HOST/collections/$COLLECTION/points/scroll" \
  -H "Content-Type: application/json" \
  -d '{
    "filter": {
      "must": [{"key": "video_id", "match": {"value": "en/curl-test"}}]
    },
    "limit": 1,
    "with_payload": false,
    "with_vector": false
  }' | python3 -c "import sys,json; pts=json.load(sys.stdin)['result']['points']; print(pts[0]['id'] if pts else '')")

if [ -z "$POINT_ID" ]; then
  echo "No points found — did the embed step succeed?"
  exit 1
fi

echo "Using point id: $POINT_ID as query proxy"

QUERY_VECTOR=$(curl -sf "$QDRANT_HOST/collections/$COLLECTION/points/$POINT_ID?with_vector=true" \
  | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin)['result']['vector']))")

echo "Running nearest-neighbour search (top 3 results)..."
curl -sf -X POST "$QDRANT_HOST/collections/$COLLECTION/points/search" \
  -H "Content-Type: application/json" \
  -d "{
    \"vector\": $QUERY_VECTOR,
    \"limit\": 3,
    \"with_payload\": true
  }" | python3 -c "
import sys, json
results = json.load(sys.stdin)['result']
for r in results:
    print(f\"  score={r['score']:.4f}  [{r['payload']['timestamp_start']}s-{r['payload']['timestamp_end']}s]  {r['payload']['text']}\")
"

echo ""
echo "Done."
