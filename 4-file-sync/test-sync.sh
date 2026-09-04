#!/usr/bin/env bash
# test-sync.sh — local smoke test for sync.sh using the filesystem as a mock remote.
#
# No cloud credentials, no Docker, no HPC needed.
#
# Usage:
#   ./4-file-sync/test-sync.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── Test workspace setup ───────────────────────────────────────────────────────

TESTDIR="$(mktemp -d)"
trap 'rm -rf "$TESTDIR"' EXIT   # always clean up on exit

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
echo "Workspace : $WORKSPACE"
echo "Mock Drive input  : $MOCK_INPUT"
echo "Mock Drive output : $MOCK_OUTPUT"

# ── Test fixtures ──────────────────────────────────────────────────────────────

# Two audio files waiting in the Drive input folder
echo "fake audio content" > "$MOCK_INPUT/interview.mp3"
echo "fake video content" > "$MOCK_INPUT/lecture.mp4"

# A completed transcript in the local output folder (ready to push back to Drive)
echo "Hello, this is the transcript." > "$WORKSPACE/sync/output/interview.txt"

run_sync() {
    WORKSPACE="$WORKSPACE" \
    DRIVE_INPUT="$MOCK_INPUT" \
    DRIVE_OUTPUT="$MOCK_OUTPUT" \
    "$SCRIPT_DIR/sync.sh"
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
