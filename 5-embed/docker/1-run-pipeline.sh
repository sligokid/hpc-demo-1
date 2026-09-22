#!/usr/bin/env bash
# End-to-end Docker pipeline demo.
# Starts all services, processes a sample file, then runs search, graph, and playlist.
#
# Usage (from any directory):
#   ./5-embed/docker/1-run-pipeline.sh
#   ./5-embed/docker/1-run-pipeline.sh inbox/en/foo.mp3 en
set -euo pipefail

cd "$(dirname "$0")/../.."

AUDIO="${1:-2-inference/audio/sligo-triathlon-club-inviting-women-to-try-a-tri.mp3}"
LANG="${2:-en}"

echo "==> Starting services (qdrant, embed-server, ollama)..."
docker compose up -d qdrant embed-server ollama

echo "==> Waiting for embed-server to be healthy..."
until docker compose exec embed-server curl -sf http://localhost:8765/health > /dev/null 2>&1; do
    echo "   not ready yet — retrying in 5s..."
    sleep 5
done
echo "   embed-server ready."

echo "Pulling llama3 model..."
docker compose exec ollama ollama pull llama3

echo "==> Running pipeline: $AUDIO (lang=$LANG)"
docker compose run --rm dev python pipeline.py \
    --ollama-host ollama:11434 \
    --file "$AUDIO" \
    --lang "$LANG"

echo "==> Semantic search demo..."
docker compose run --rm dev python search.py \
    --query "triathlon" \
    --qdrant-host qdrant:6333

echo "==> Building knowledge graph..."
docker compose run --rm dev python 6-graph/graph.py \
    --qdrant-host qdrant:6333 \
    --output sync/output/graph.json

echo "==> Generating personalised playlist..."
docker compose run --rm dev python 6-graph/playlist.py \
    --user engineer@org.com \
    --qdrant-host qdrant:6333

echo "==> Pipeline complete for one file - this is a smoke test."
