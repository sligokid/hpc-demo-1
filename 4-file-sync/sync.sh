#!/usr/bin/env bash
# sync.sh — poll Google Drive (or any rclone remote) and sync files to/from HPC.
#
# Download:  $DRIVE_INPUT  → $WORKSPACE/sync/input/
# Upload:    $WORKSPACE/sync/output/ → $DRIVE_OUTPUT
#
# Newly arrived input files are appended to $WORKSPACE/logs/sync-manifest.txt.
# All configuration is via environment variables so the same script works with
# a local mock remote, Google Drive, GCS, or S3 — no code changes required.
#
# Usage:
#   WORKSPACE=/tmp/test RCLONE_REMOTE=local: ./sync.sh
#   ./sync.sh   # inside container, uses defaults

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
WORKSPACE="${WORKSPACE:-/workspace}"
RCLONE_REMOTE="${RCLONE_REMOTE:-gdrive}"
DRIVE_INPUT="${DRIVE_INPUT:-${RCLONE_REMOTE}:whisper-sync/input}"
DRIVE_OUTPUT="${DRIVE_OUTPUT:-${RCLONE_REMOTE}:whisper-sync/output}"

# LOCAL_INPUT="${WORKSPACE}/sync/input"
# LOCAL_OUTPUT="${WORKSPACE}/sync/output"
LOCAL_INPUT="${WORKSPACE}/inbox"
LOCAL_OUTPUT="${WORKSPACE}/results"
LOG_DIR="${WORKSPACE}/logs"
MANIFEST="${LOG_DIR}/sync-manifest.txt"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
LOG_FILE="${LOG_DIR}/sync-${TIMESTAMP}.out"

# ── Setup ─────────────────────────────────────────────────────────────────────
mkdir -p "$LOCAL_INPUT" "$LOCAL_OUTPUT" "$LOG_DIR"
touch "$MANIFEST"

# Tee all output to the per-run log file
exec > >(tee -a "$LOG_FILE") 2>&1

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"; }

log "sync start"
log "  WORKSPACE    = $WORKSPACE"
log "  DRIVE_INPUT  = $DRIVE_INPUT"
log "  DRIVE_OUTPUT = $DRIVE_OUTPUT"

# ── Snapshot local input before download ──────────────────────────────────────
BEFORE="$(mktemp)"
find "$LOCAL_INPUT" -type f | sort > "$BEFORE"

# ── Download: Drive input → local input ───────────────────────────────────────
log "download $DRIVE_INPUT → $LOCAL_INPUT"
rclone copy "$DRIVE_INPUT" "$LOCAL_INPUT" \
    --transfers 4 \
    --log-level INFO

# ── Detect newly arrived files ────────────────────────────────────────────────
AFTER="$(mktemp)"
find "$LOCAL_INPUT" -type f | sort > "$AFTER"

# Lines in AFTER but not in BEFORE = new arrivals this run
NEW_FILES="$(comm -13 "$BEFORE" "$AFTER")"
rm -f "$BEFORE" "$AFTER"

new_count=0
if [[ -n "$NEW_FILES" ]]; then
    while IFS= read -r f; do
        # Idempotency: skip if already recorded in manifest
        if grep -qxF "$f" "$MANIFEST" 2>/dev/null; then
            log "manifest already contains: $f"
            continue
        fi
        echo "$f" >> "$MANIFEST"
        log "manifest ← $f"
        new_count=$((new_count + 1))
    done <<< "$NEW_FILES"
fi

log "$new_count new file(s) added to manifest"

# ── Upload: local output → Drive output ───────────────────────────────────────
log "upload $LOCAL_OUTPUT → $DRIVE_OUTPUT"
rclone copy "$LOCAL_OUTPUT" "$DRIVE_OUTPUT" \
    --transfers 4 \
    --log-level INFO

log "sync complete"
