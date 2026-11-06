#!/usr/bin/env bats
# Validate that CLAUDE.md stays in sync with the repository layout.
#
# Tests confirm that every file path mentioned in the Architecture table of
# CLAUDE.md points to a file that actually exists, and that key commands
# documented in CLAUDE.md reference real targets.
#
# Run:
#   bats tests/

REPO_ROOT="$BATS_TEST_DIRNAME/.."
CLAUDE_MD="$REPO_ROOT/CLAUDE.md"

# ---------------------------------------------------------------------------
# CLAUDE.md itself
# ---------------------------------------------------------------------------

@test "CLAUDE.md exists" {
    [ -f "$CLAUDE_MD" ]
}

# ---------------------------------------------------------------------------
# Architecture table — all documented paths must exist
# ---------------------------------------------------------------------------

@test "1-train/train.py exists (Architecture table)" {
    [ -f "$REPO_ROOT/1-train/train.py" ]
}

@test "1-train/hpc/train-sbatch-gpu.sh exists (Architecture table)" {
    [ -f "$REPO_ROOT/1-train/hpc/train-sbatch-gpu.sh" ]
}

@test "1-train/hpc/train-sbatch-cpu.sh exists (Architecture table)" {
    [ -f "$REPO_ROOT/1-train/hpc/train-sbatch-cpu.sh" ]
}

@test "2-inference/infer.py exists (Architecture table, primary inference module)" {
    [ -f "$REPO_ROOT/2-inference/infer.py" ]
}

@test "2-inference/infer-30-secs.py exists (Architecture table)" {
    [ -f "$REPO_ROOT/2-inference/infer-30-secs.py" ]
}

@test "2-inference/infer-full.py exists (Architecture table)" {
    [ -f "$REPO_ROOT/2-inference/infer-full.py" ]
}

@test "3-analyze/analyze.py exists (Architecture table)" {
    [ -f "$REPO_ROOT/3-analyze/analyze.py" ]
}

@test "4-file-sync/sync.sh exists (Architecture table)" {
    [ -f "$REPO_ROOT/4-file-sync/sync.sh" ]
}

@test "5-sentiment/sentiment.py exists (Architecture table)" {
    [ -f "$REPO_ROOT/5-sentiment/sentiment.py" ]
}

@test "6-embed/embed_server.py exists (Architecture table)" {
    [ -f "$REPO_ROOT/6-embed/embed_server.py" ]
}

@test "7-index/index_server.py exists (Architecture table)" {
    [ -f "$REPO_ROOT/7-index/index_server.py" ]
}

@test "8-search/search.py exists (Architecture table)" {
    [ -f "$REPO_ROOT/8-search/search.py" ]
}

@test "9-graph/graph.py exists (Architecture table)" {
    [ -f "$REPO_ROOT/9-graph/graph.py" ]
}

@test "9-graph/playlist.py exists (Architecture table)" {
    [ -f "$REPO_ROOT/9-graph/playlist.py" ]
}

@test "10-agent/agent.py exists (Architecture table)" {
    [ -f "$REPO_ROOT/10-agent/agent.py" ]
}

@test "11-sop/sop.py exists (Architecture table)" {
    [ -f "$REPO_ROOT/11-sop/sop.py" ]
}

@test "11-sop/teleprompter.py exists (Architecture table)" {
    [ -f "$REPO_ROOT/11-sop/teleprompter.py" ]
}

@test "pipeline.py exists (Architecture table)" {
    [ -f "$REPO_ROOT/pipeline.py" ]
}

# ---------------------------------------------------------------------------
# Commands section — CLI paths in CLAUDE.md must resolve to real files
# ---------------------------------------------------------------------------

@test "CLAUDE.md references correct inference CLI path (2-inference/infer.py, not root infer.py)" {
    # The documented command must use the sub-directory path, not a root-level infer.py
    grep -q "2-inference/infer.py" "$CLAUDE_MD"
}

@test "No stale root-level infer.py reference in CLAUDE.md" {
    # Ensure the old incorrect path is gone (the file at repo root never existed)
    run grep -P "^python infer\.py" "$CLAUDE_MD"
    [ "$status" -ne 0 ]
}

# ---------------------------------------------------------------------------
# Local Development section — Makefile target must exist
# ---------------------------------------------------------------------------

@test "Makefile defines the 'test' target referenced in CLAUDE.md" {
    grep -qE "^test[[:space:]]*:" "$REPO_ROOT/Makefile"
}
