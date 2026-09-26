#!/bin/bash
# Reset Qdrant: stop E-qdrant and F-index, wipe storage, restart both services.
#
# Run from the project root on a login node:
#   bash reset-qdrant.sh

set -euo pipefail

SCRATCH=${SCRATCH:-/scratch/project_465003359/mcgowank}
QDRANT_STORAGE_DIR=$SCRATCH/qdrant-storage
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "============================================"
echo "Reset Qdrant"
echo "Storage : $QDRANT_STORAGE_DIR"
echo "============================================"

# Stop dependent services first
echo "Cancelling services.."
scancel --me

echo "Waiting 15s for services to stop..."
sleep 15

# Wipe storage
echo "Deleting $QDRANT_STORAGE_DIR ..."
rm -rf "$QDRANT_STORAGE_DIR"
echo "Storage deleted."

echo "Done. Collections will be recreated on first pipeline run."
