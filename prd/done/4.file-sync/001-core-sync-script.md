## Parent PRD

`issues/prd.md`

## What to build

Write `3-sync/sync.sh` — the core sync logic that runs inside the container. It performs two rclone copy operations sequentially (Drive `input/` → local `sync/input/`, then local `sync/output/` → Drive `output/`), detects newly arrived files by comparing against a snapshot, and appends their absolute paths to `logs/sync-manifest.txt`.

All configuration comes from environment variables (`RCLONE_REMOTE`, `DRIVE_INPUT`, `DRIVE_OUTPUT`, `WORKSPACE`) so the same script works with a local mock remote, a real Google Drive remote, GCS, or S3 — no code changes required.

Verify locally by installing rclone directly and running the script with a `local:` remote pointing at a temp directory. No Docker, no HPC, no live Drive credentials needed at this stage.

See the Modules and Interfaces sections of the parent PRD for the full contract.

## Acceptance criteria

- [ ] `3-sync/sync.sh` exists and is executable
- [ ] Running with a `local:` remote copies a test file from the mock input source into `sync/input/`
- [ ] Running with a `local:` remote copies a file from `sync/output/` into the mock output destination
- [ ] `logs/sync-manifest.txt` is created if absent and the newly arrived file path is appended
- [ ] A second run with no new input files does not append duplicate entries to the manifest
- [ ] A file already present in `sync/input/` (same size+modtime) is not re-copied on subsequent runs
- [ ] All paths inside the script are relative to `$WORKSPACE` (defaults to `/workspace`) so the script works both locally and inside the container

## Blocked by

None — can start immediately.

## User stories addressed

- User story 1 (input files arrive on HPC automatically)
- User story 2 (output files pushed back to Drive)
- User story 3 (5-minute polling interval — script runs one cycle; interval set by scheduler)
- User story 6 (manifest written after each poll)
- User story 7 (manifest appends, does not overwrite)
- User story 8 (separate input/output directories)
- User story 11 (sync is idempotent)
- User story 12 (rclone skips unchanged files)
- User story 14 (logs written to `logs/` directory)
- User story 15 (cloud provider swappable via env var)
- User story 16 (manifest records absolute paths)
- User story 17 (output sync scoped to output directory only)
