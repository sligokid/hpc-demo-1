#!/usr/bin/env bash
# Smoke-test the embed-server with plain curl.
# Prerequisites: embed-server running (script 1).
# Run from the project root or from this directory.
set -euo pipefail

EMBED_HOST="${EMBED_HOST:-http://localhost:8765}"

echo "=== 1. Health check ==="
curl -sf "$EMBED_HOST/health" | python3 -m json.tool

echo ""
echo "=== 2. Embed sample transcript chunks via POST /embed ==="
curl -sf -X POST "$EMBED_HOST/embed" \
  -H "Content-Type: application/json" \
  -d '{
    "chunks": [
      {"text": "Machine learning models learn patterns from data automatically.", "timestamp_start": 0.0,  "timestamp_end": 4.2},
      {"text": "Deep neural networks are used for image and speech recognition.", "timestamp_start": 4.2,  "timestamp_end": 8.7},
      {"text": "The training loop updates weights using gradient descent.",       "timestamp_start": 8.7,  "timestamp_end": 13.1}
    ]
  }' | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'vectors returned: {len(data[\"vectors\"])}')
for v in data['vectors']:
    print(f'  [{v[\"ts_start\"]}s-{v[\"ts_end\"]}s]  dim={len(v[\"vector\"])}  text={v[\"text\"][:60]}')
"

echo ""
echo "Done."
