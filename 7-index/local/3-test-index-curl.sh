#!/usr/bin/env bash
# Smoke-test the index-server and Qdrant with plain curl.
# Uses a synthetic 1024-dim vector so the embed-server is not required.
# Prerequisites: Qdrant running (script 1), index-server running (script 2).
# Run from the project root or from this directory.
set -euo pipefail

INDEX_HOST="${INDEX_HOST:-http://localhost:8766}"
QDRANT_HOST="${QDRANT_HOST:-http://localhost:6333}"
VIDEO_ID="en/curl-test"

# Build a synthetic 1024-dim unit vector once and reuse it.
FAKE_VECTOR=$(python3 -c "import json, math; v=[round(1/math.sqrt(1024),6)]*1024; print(json.dumps(v))")

echo "=== 1. Health check ==="
curl -sf "$INDEX_HOST/health" | python3 -m json.tool

echo ""
echo "=== 2. Index sample vectors via POST /index ==="
curl -sf -X POST "$INDEX_HOST/index" \
  -H "Content-Type: application/json" \
  -d "{
    \"video_id\": \"$VIDEO_ID\",
    \"file\": \"inbox/en/curl-test.mp3\",
    \"lang\": \"en\",
    \"vectors\": [
      {\"text\": \"Machine learning models learn patterns from data automatically.\", \"ts_start\": 0.0,  \"ts_end\": 4.2,  \"vector\": $FAKE_VECTOR},
      {\"text\": \"Deep neural networks are used for image and speech recognition.\", \"ts_start\": 4.2,  \"ts_end\": 8.7,  \"vector\": $FAKE_VECTOR},
      {\"text\": \"The training loop updates weights using gradient descent.\",        \"ts_start\": 8.7,  \"ts_end\": 13.1, \"vector\": $FAKE_VECTOR}
    ]
  }" | python3 -m json.tool

echo ""
echo "=== 3. Index metadata via POST /metadata ==="
curl -sf -X POST "$INDEX_HOST/metadata" \
  -H "Content-Type: application/json" \
  -d "{
    \"video_id\": \"$VIDEO_ID\",
    \"file\": \"inbox/en/curl-test.mp3\",
    \"lang\": \"en\",
    \"title\": \"Curl Test Video\",
    \"tags\": [\"machine-learning\", \"neural-networks\"],
    \"sentiment_label\": \"neutral\",
    \"sentiment_score\": 0.0
  }" | python3 -m json.tool

echo ""
echo "=== 4. Verify chunks stored in Qdrant (video_chunks scroll) ==="
curl -sf -X POST "$QDRANT_HOST/collections/video_chunks/points/scroll" \
  -H "Content-Type: application/json" \
  -d "{
    \"filter\": {\"must\": [{\"key\": \"video_id\", \"match\": {\"value\": \"$VIDEO_ID\"}}]},
    \"limit\": 10,
    \"with_payload\": true,
    \"with_vector\": false
  }" | python3 -c "
import sys, json
pts = json.load(sys.stdin)['result']['points']
print(f'chunks in video_chunks: {len(pts)}')
for p in pts:
    pl = p['payload']
    print(f'  [{pl[\"timestamp_start\"]}s-{pl[\"timestamp_end\"]}s]  {pl[\"text\"][:60]}')
"

echo ""
echo "=== 5. Verify metadata stored in Qdrant (video_metadata scroll) ==="
curl -sf -X POST "$QDRANT_HOST/collections/video_metadata/points/scroll" \
  -H "Content-Type: application/json" \
  -d "{
    \"filter\": {\"must\": [{\"key\": \"video_id\", \"match\": {\"value\": \"$VIDEO_ID\"}}]},
    \"limit\": 1,
    \"with_payload\": true,
    \"with_vector\": false
  }" | python3 -c "
import sys, json
pts = json.load(sys.stdin)['result']['points']
print(f'records in video_metadata: {len(pts)}')
if pts:
    pl = pts[0]['payload']
    print(f'  title          : {pl.get(\"title\", \"n/a\")}')
    print(f'  tags           : {pl.get(\"tags\", [])}')
    print(f'  sentiment_label: {pl.get(\"sentiment_label\", \"n/a\")}')
    print(f'  sentiment_score: {pl.get(\"sentiment_score\", \"n/a\")}')
"

echo ""
echo "Done."
