#!/usr/bin/env bats
# Shell-script tests for ollama-serve.sh, ollama-pull.sh, and analyze-batch.sh.
# Mocks external commands (curl, singularity, ss, rocm-smi) at the shell boundary.
#
# Run:
#   bats tests/
#
# Install bats:
#   brew install bats-core          # macOS
#   apt-get install bats            # Debian/Ubuntu

OLLAMA_SERVE="$BATS_TEST_DIRNAME/../ollama/hpc/2-ollama-serve-sbatch.sh"
OLLAMA_PULL="$BATS_TEST_DIRNAME/../ollama/hpc/3-ollama-pull.sh"
ANALYZE_BATCH="$BATS_TEST_DIRNAME/../analyze-batch.sh"

setup() {
    SCRATCH=$(mktemp -d)
    export SCRATCH
    export OLLAMA_SIF="$SCRATCH/ollama.sif"
    touch "$OLLAMA_SIF"

    MOCK_DIR="$SCRATCH/bin"
    mkdir -p "$MOCK_DIR"
    export PATH="$MOCK_DIR:$PATH"

    # SLURM env vars required by the scripts
    export SLURM_JOB_ID=99999
    export SLURM_ARRAY_TASK_ID=0

    # Working dir for serve script's relative `mkdir -p logs`
    mkdir -p "$SCRATCH/logs"

    # --- mock: ss (no port in use) ---
    cat > "$MOCK_DIR/ss" <<'MOCK'
#!/bin/bash
exit 0
MOCK
    chmod +x "$MOCK_DIR/ss"

    # --- mock: rocm-smi ---
    cat > "$MOCK_DIR/rocm-smi" <<'MOCK'
#!/bin/bash
exit 1
MOCK
    chmod +x "$MOCK_DIR/rocm-smi"

    # --- mock: singularity ---
    # SINGULARITY_SERVE_SLEEP  - seconds the mocked serve process sleeps (default 0)
    # MOCK_OLLAMA_LIST         - output for `ollama list` calls (default empty)
    cat > "$MOCK_DIR/singularity" <<'MOCK'
#!/bin/bash
case "$*" in
    *" serve"*)
        sleep "${SINGULARITY_SERVE_SLEEP:-0}"
        ;;
    *"ollama list"*)
        printf '%s\n' "${MOCK_OLLAMA_LIST:-}"
        ;;
    *"ollama pull"*)
        : # no-op
        ;;
esac
exit 0
MOCK
    chmod +x "$MOCK_DIR/singularity"
}

teardown() {
    rm -rf "$SCRATCH"
}

# ---------------------------------------------------------------------------
# Helper: write a curl mock driven by a counter file.
#   CURL_COUNTER_FILE  - auto-set to $SCRATCH/.curl_count
#   CURL_SUCCEED_ON    - succeed (exit 0) on this call number and beyond (default 1)
# ---------------------------------------------------------------------------
_write_curl_counter_mock() {
    export CURL_COUNTER_FILE="$SCRATCH/.curl_count"
    echo 0 > "$CURL_COUNTER_FILE"
    cat > "$MOCK_DIR/curl" <<'MOCK'
#!/bin/bash
COUNT=$(cat "${CURL_COUNTER_FILE}" 2>/dev/null || echo 0)
COUNT=$((COUNT + 1))
echo "$COUNT" > "${CURL_COUNTER_FILE}"
if [ "$COUNT" -ge "${CURL_SUCCEED_ON:-1}" ]; then
    exit 0
else
    exit 1
fi
MOCK
    chmod +x "$MOCK_DIR/curl"
}

# ---------------------------------------------------------------------------
# Helper: start serve script in background using exec so SERVE_PID is the
# bash PID (enabling SIGTERM delivery to the script, not just a subshell).
# ---------------------------------------------------------------------------
_start_serve_bg() {
    (cd "$SCRATCH"; exec bash "$OLLAMA_SERVE" 2>/dev/null) &
    SERVE_PID=$!
}

# ---------------------------------------------------------------------------
# Helper: stop a background serve process and wait for it to finish.
# ---------------------------------------------------------------------------
_stop_serve() {
    local pid=${1:-$SERVE_PID}
    kill -TERM "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
}

# ---------------------------------------------------------------------------
# Helper: poll until a file exists, timeout after ~5 s.
# ---------------------------------------------------------------------------
_wait_for_file() {
    local path=$1
    local waited=0
    while [ $waited -lt 100 ] && [ ! -f "$path" ]; do
        sleep 0.05
        waited=$((waited + 1))
    done
}

# ---------------------------------------------------------------------------
# Helper: poll until a file disappears, timeout after ~3 s.
# ---------------------------------------------------------------------------
_wait_for_file_gone() {
    local path=$1
    local waited=0
    while [ $waited -lt 60 ] && [ -f "$path" ]; do
        sleep 0.05
        waited=$((waited + 1))
    done
}

# ===========================================================================
# ollama-serve.sh — health-check loop
# ===========================================================================

@test "ollama-serve.sh retries curl before writing the endpoint file" {
    # curl fails on calls 1 and 2, succeeds on call 3
    export CURL_SUCCEED_ON=3
    _write_curl_counter_mock
    # Keep serve alive so we can observe the endpoint file before EXIT trap fires
    export SINGULARITY_SERVE_SLEEP=30

    _start_serve_bg

    # Wait for endpoint file to appear (written only after curl succeeds)
    _wait_for_file "$SCRATCH/ollama.endpoint"

    # Assert file exists while the script is still running
    [ -f "$SCRATCH/ollama.endpoint" ]

    # curl must have been called at least 3 times (2 failures + 1 success)
    CALL_COUNT=$(cat "$CURL_COUNTER_FILE")
    [ "$CALL_COUNT" -ge 3 ]

    _stop_serve
}

@test "ollama-serve.sh endpoint file contains hostname:port" {
    export CURL_SUCCEED_ON=1
    _write_curl_counter_mock
    export SINGULARITY_SERVE_SLEEP=30

    _start_serve_bg
    _wait_for_file "$SCRATCH/ollama.endpoint"

    [ -f "$SCRATCH/ollama.endpoint" ]
    CONTENT=$(cat "$SCRATCH/ollama.endpoint")
    # must be host:port format
    [[ "$CONTENT" == *:* ]]

    _stop_serve
}

# ===========================================================================
# ollama-serve.sh — cleanup trap
# ===========================================================================

@test "ollama-serve.sh cleanup trap removes endpoint file on SIGTERM" {
    export CURL_SUCCEED_ON=1
    _write_curl_counter_mock
    # Keep serve alive so SIGTERM arrives while script is waiting
    export SINGULARITY_SERVE_SLEEP=60

    _start_serve_bg

    # Wait for endpoint file to be created
    _wait_for_file "$SCRATCH/ollama.endpoint"
    [ -f "$SCRATCH/ollama.endpoint" ]

    # Send SIGTERM to the bash script and wait for it to exit
    kill -TERM "$SERVE_PID" 2>/dev/null || true
    wait "$SERVE_PID" 2>/dev/null || true

    # Allow a brief moment for the EXIT trap to run
    _wait_for_file_gone "$SCRATCH/ollama.endpoint"

    [ ! -f "$SCRATCH/ollama.endpoint" ]
}

# ===========================================================================
# analyze-batch.sh — missing discovery file
# ===========================================================================

@test "analyze-batch.sh exits non-zero when endpoint discovery file is absent" {
    rm -f "$SCRATCH/ollama.endpoint"

    TRANSCRIPT_DIR="$SCRATCH/transcripts"
    mkdir -p "$TRANSCRIPT_DIR"

    run bash "$ANALYZE_BATCH" "$TRANSCRIPT_DIR"
    [ "$status" -ne 0 ]
}

@test "analyze-batch.sh prints descriptive error when endpoint file is absent" {
    rm -f "$SCRATCH/ollama.endpoint"

    TRANSCRIPT_DIR="$SCRATCH/transcripts"
    mkdir -p "$TRANSCRIPT_DIR"

    run bash "$ANALYZE_BATCH" "$TRANSCRIPT_DIR" 2>&1
    [[ "$output" == *"endpoint"* ]]
}

# ===========================================================================
# ollama-pull.sh — successful pull
# ===========================================================================

@test "ollama-pull.sh exits 0 when model appears in ollama list" {
    echo "testnode:11434" > "$SCRATCH/ollama.endpoint"
    export MOCK_OLLAMA_LIST="llama3   latest   abc123   4.7 GB   2 hours ago"

    run bash "$OLLAMA_PULL" llama3
    [ "$status" -eq 0 ]
}

# ===========================================================================
# ollama-pull.sh — failed pull
# ===========================================================================

@test "ollama-pull.sh exits non-zero when model is absent from ollama list" {
    echo "testnode:11434" > "$SCRATCH/ollama.endpoint"
    export MOCK_OLLAMA_LIST=""

    run bash "$OLLAMA_PULL" llama3
    [ "$status" -ne 0 ]
}
