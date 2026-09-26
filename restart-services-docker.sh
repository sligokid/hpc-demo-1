#!/usr/bin/env bash
# Restart all persistent services defined in docker-compose.yml.
# Stops and removes the service containers, then brings them back up,
# waiting for each health check to pass before continuing.
#
# Services restarted (in dependency order):
#   ollama       — Llama 3 inference (port 11434)
#   qdrant       — vector database   (port 6333)
#   embed-server — encoding service  (port 8765)
#   index-server — indexing service  (port 8766)
#
# The dev container is intentionally excluded — it is ephemeral and
# started on demand by pipeline-docker.sh.
#
# Usage:
#   ./restart-services-docker.sh           # restart all services
#   ./restart-services-docker.sh --build   # rebuild images before restarting

set -euo pipefail

cd "$(dirname "$0")"

BUILD_FLAG=""
if [[ "${1:-}" == "--build" ]]; then
    BUILD_FLAG="--build"
fi

SERVICES="ollama qdrant embed-server index-server"

echo "============================================"
echo "Restarting services: $SERVICES"
echo "Started : $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "============================================"

# Stop and remove the service containers (leaves volumes intact).
echo ""
echo "--- Stopping services ---"
docker compose stop $SERVICES
docker compose rm -f $SERVICES

# Bring services back up in detached mode.
echo ""
echo "--- Starting services ---"
# shellcheck disable=SC2086
docker compose up -d $BUILD_FLAG $SERVICES

# Wait for each service health check to pass before proceeding.
echo ""
echo "--- Waiting for health checks ---"

_wait_healthy() {
    local service="$1"
    local timeout="${2:-120}"
    local elapsed=0
    echo -n "  $service "
    local cid
    cid=$(docker compose ps -q "$service" 2>/dev/null)
    until [ "$(docker inspect --format='{{.State.Health.Status}}' "$cid" 2>/dev/null)" = "healthy" ]; do
        if [ "$elapsed" -ge "$timeout" ]; then
            echo ""
            echo "ERROR: $service did not become healthy within ${timeout}s" >&2
            docker compose logs --tail=20 "$service" >&2
            exit 1
        fi
        echo -n "."
        sleep 5
        elapsed=$((elapsed + 5))
    done
    echo " healthy (${elapsed}s)"
}

_wait_healthy ollama       180   # first-run model pull can be slow
echo ""
echo "============================================"
echo "--- Ensuring llama3 is pulled... ---"
docker compose exec ollama ollama pull llama3:latest

_wait_healthy qdrant        60
_wait_healthy embed-server 180   # model load takes ~90s on CPU
_wait_healthy index-server  60

echo ""
echo "============================================"
echo "All services healthy."
echo "  ollama       : http://localhost:11434"
echo "  qdrant        : http://localhost:6333  (dashboard: http://localhost:6333/dashboard)"
echo "  embed-server  : http://localhost:8765/health"
echo "  index-server  : http://localhost:8766/health"
echo "Finished : $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "============================================"
