#!/usr/bin/env bash
# test-local.sh — end-to-end Docker test for the whisper-sync image.
#
# Builds the image for linux/amd64 (the target platform for LUMI SIF conversion),
# then runs three sync cycles using local directories as a mock Google Drive.
# No cloud credentials required.
#
# Usage:
#   ./3-sync/docker/test-local.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
IMAGE="whisper-sync"

# ── Build ──────────────────────────────────────────────────────────────────────

echo "================================================"
echo " BUILD"
echo "================================================"
docker buildx build \
    --platform linux/amd64 \
    --load \
    --tag "$IMAGE" \
    "$REPO_ROOT/3-sync"

# ── Test workspace setup ───────────────────────────────────────────────────────

TESTDIR="$(mktemp -d)"
trap 'rm -rf "$TESTDIR"' EXIT

WORKSPACE="$TESTDIR/workspace"
MOCK_INPUT="$TESTDIR/drive/input"   # simulates Google Drive input folder
MOCK_OUTPUT="$TESTDIR/drive/output" # simulates Google Drive output folder

mkdir -p "$WORKSPACE/sync/input"
mkdir -p "$WORKSPACE/sync/output"
mkdir -p "$WORKSPACE/logs"
mkdir -p "$MOCK_INPUT"
mkdir -p "$MOCK_OUTPUT"

echo ""
echo "================================================"
echo " SETUP"
echo "================================================"
echo "Workspace        : $WORKSPACE"
echo "Mock Drive input : $MOCK_INPUT"
echo "Mock Drive output: $MOCK_OUTPUT"

# Two audio files waiting in the Drive input folder
echo "fake audio content" > "$MOCK_INPUT/interview.mp3"
echo "fake video content" > "$MOCK_INPUT/lecture.mp4"

# A completed transcript in the local output folder
echo "Hello, this is the transcript." > "$WORKSPACE/sync/output/interview.txt"

run_sync() {
    docker run --rm \
        --platform linux/amd64 \
        -v "$WORKSPACE:/workspace" \
        -v "$MOCK_INPUT:/mock/input" \
        -v "$MOCK_OUTPUT:/mock/output" \
        -e WORKSPACE=/workspace \
        -e DRIVE_INPUT=/mock/input \
        -e DRIVE_OUTPUT=/mock/output \
        "$IMAGE"
}

# ── RUN 1: initial sync ────────────────────────────────────────────────────────

echo ""
echo "================================================"
echo " RUN 1 — initial sync"
echo " Expect: 2 files downloaded, 1 file uploaded,"
echo "         manifest has 2 entries"
echo "================================================"
run_sync

echo ""
echo "--- sync/input (should contain interview.mp3 + lecture.mp4) ---"
ls "$WORKSPACE/sync/input/"

echo ""
echo "--- drive/output (should contain interview.txt) ---"
ls "$MOCK_OUTPUT/"

echo ""
echo "--- manifest (should have 2 lines) ---"
cat "$WORKSPACE/logs/sync-manifest.txt"

# ── RUN 2: idempotency ─────────────────────────────────────────────────────────

echo ""
echo "================================================"
echo " RUN 2 — run again with no new files"
echo " Expect: nothing transferred, manifest unchanged"
echo "================================================"
run_sync

echo ""
echo "--- manifest (should still have 2 lines) ---"
cat "$WORKSPACE/logs/sync-manifest.txt"

# ── RUN 3: new file arrives ────────────────────────────────────────────────────

echo ""
echo "================================================"
echo " RUN 3 — new file added to Drive input"
echo " Expect: only the new file added to manifest"
echo "================================================"
echo "brand new audio" > "$MOCK_INPUT/keynote.mp3"
run_sync

echo ""
echo "--- manifest (should now have 3 lines) ---"
cat "$WORKSPACE/logs/sync-manifest.txt"

MANIFEST_LINES="$(wc -l < "$WORKSPACE/logs/sync-manifest.txt")"
if [[ "$MANIFEST_LINES" -eq 3 ]]; then
    echo ""
    echo "✓ All tests passed"
else
    echo ""
    echo "✗ Expected 3 manifest lines, got $MANIFEST_LINES"
    exit 1
fi
