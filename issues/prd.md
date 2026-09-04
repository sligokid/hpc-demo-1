# PRD: Cloud-to-HPC File Sync Pipeline for Whisper Batch Inference

## Problem Statement

Audio and video files for Whisper batch inference need to move reliably between a Google Drive folder (accessible to clients or operators) and the LUMI HPC login node where inference jobs are submitted. Currently there is no automated mechanism to deliver input files to HPC or to return transcription results back to the cloud. This creates a manual bottleneck: files must be uploaded to HPC by hand, and results must be retrieved manually. As batch volume grows, this is not sustainable.

A secondary problem is testability: HPC sync behaviour must be verifiable locally before deploying to LUMI, without access to the HPC environment.

## Solution

Introduce a dedicated sync stage (`3-sync/`) that packages rclone and the sync script into a Docker image. The image can be run locally for full end-to-end testing, then converted to a Singularity Image Format (SIF) file for deployment on LUMI. On LUMI, a self-resubmitting SLURM job on the CPU partition runs the SIF every 5 minutes via `singularity exec`, polling Google Drive for new audio/video files and pushing completed transcription outputs back up. A manifest file lists newly arrived files for manual inference job submission. rclone is used as the transport abstraction, making the cloud provider swappable to GCS or S3 via a config change alone.

## User Stories

1. As a developer, I want new audio/video files placed in a Google Drive folder to appear automatically on the HPC filesystem, so that I do not need to manually transfer files before submitting inference jobs.
2. As a developer, I want completed transcription output files to be automatically uploaded back to a Google Drive results folder, so that results are accessible without logging into HPC.
3. As a developer, I want the sync to run on a 5-minute polling interval, so that end-to-end latency between file upload and availability on HPC is predictable and acceptable for batch workflows.
4. As a developer, I want the sync to run as a self-resubmitting SLURM job on the CPU partition, so that it operates within HPC policy without requiring crontab access.
5. As a developer, I want the sync job to self-resubmit after each run, so that the pipeline continues running without manual intervention after the initial submission.
6. As a developer, I want the sync to write a manifest file listing newly arrived input files after each poll, so that I can review and submit SLURM inference jobs in a controlled, deliberate way.
7. As a developer, I want the manifest to append new entries rather than overwrite, so that files are not silently lost between polling cycles if I don't check between runs.
8. As a developer, I want input files and output files to use separate Drive folders and separate HPC directories, so that there is no ambiguity about data flow direction and no conflict resolution is needed.
9. As a developer, I want rclone credentials stored with restrictive file permissions (600), so that the OAuth2 refresh token is not readable by other users on the shared login node.
10. As a developer, I want the rclone config to be set up once interactively on my local machine and then copied to HPC, so that no browser or interactive session is needed on the HPC node itself.
11. As a developer, I want the sync to be idempotent, so that re-running it does not duplicate files or manifest entries.
12. As a developer, I want rclone to skip files that already exist at the destination with matching size and modification time, so that bandwidth and API quota are not wasted on unchanged files.
13. As a developer, I want the SLURM sync job to request minimal resources (1 CPU core, low memory, short wall time), so that it does not consume project allocation unnecessarily.
14. As a developer, I want sync logs written per-run to the existing `logs/` directory, so that I can diagnose transfer failures without separate tooling.
15. As a developer, I want the sync architecture to support swapping Google Drive for GCS or S3 with only a rclone config change, so that migrating to a production cloud provider requires no code changes.
16. As a developer, I want the manifest to record the absolute HPC path of each newly arrived file, so that inference job submission scripts can consume it directly without path manipulation.
17. As a developer, I want output sync to push only files in the designated output directory, not the entire scratch space, so that unrelated project files are never accidentally uploaded to Drive.
18. As a developer, I want the sync job submission script to follow the same conventions as existing SLURM scripts in the repo (account, partition, binding style), so that the codebase remains consistent.
19. As a developer, I want a one-time setup guide for rclone + Google Drive OAuth2 config generation, so that onboarding a new HPC user or rotating credentials is straightforward.
20. As a developer, I want the sync pipeline packaged as a Docker image, so that I can run and test it fully on my laptop before deploying to HPC.
21. As a developer, I want to test the full sync cycle locally using Docker with a local filesystem as the mock remote, so that I can validate sync logic and manifest output without live Drive credentials or HPC access.
22. As a developer, I want the Docker image to be convertible to a Singularity SIF file with a single command, so that deploying to LUMI requires no changes to the image contents.
23. As a developer, I want the SLURM job to run the sync via `singularity exec` on the SIF, consistent with existing HPC scripts in the repo, so that the container runtime is uniform across all pipeline stages.
24. As a developer, I want the SIF file stored in the project scratch directory alongside the existing `whisper-hpc.sif`, so that all container images are managed in one place.

## Implementation Decisions

### Modules

**`3-sync/Dockerfile` — Container image definition**
- Base image: `rclone/rclone:latest` (official minimal image, Alpine-based, contains only rclone binary)
- Copies `sync.sh` into the image at `/usr/local/bin/sync.sh`
- Sets `sync.sh` as the default entrypoint
- No Python, no GPU libraries — purely for network I/O
- Built locally with `docker build`, pushed to Docker Hub or kept local, converted to SIF via `singularity build`

**`3-sync/sync.sh` — Core sync logic (runs inside the container)**
- Runs two rclone copy operations sequentially:
  1. Drive `input/` → `/workspace/sync/input/` (download new files)
  2. `/workspace/sync/output/` → Drive `output/` (upload new results)
- After the download pass, compares current state of `/workspace/sync/input/` against a snapshot file to detect newly arrived files
- Appends newly arrived absolute paths to `/workspace/logs/sync-manifest.txt` (creates the file if absent)
- Writes a timestamped log entry to `/workspace/logs/sync-<timestamp>.out`
- Configured entirely via environment variables — no hardcoded paths or remote names
- Is idempotent: rclone's default behaviour skips files with matching size+modtime

**`3-sync/docker/test-local.sh` — Local test runner**
- Runs the Docker image with a `rclone local:` remote pointing at a temp directory, simulating Drive
- Mounts a local `sync/` and `logs/` directory to verify manifest output and file arrival
- Validates the full sync cycle on a developer laptop with no cloud credentials required

**`3-sync/hpc/sync-sbatch.sh` — SLURM job definition**
- SLURM directives: `--account project_465003209`, `--partition=small` (CPU partition), `--time=00:10:00`, `--ntasks=1`, `--cpus-per-task=1`, `--mem=4GB`
- Resolves project root via `SLURM_SUBMIT_DIR`, consistent with `1-train/hpc/` conventions
- Runs the sync via `singularity exec --bind "$PROJECT_ROOT:/workspace" "$SIF" bash -c "..."`
- Mounts rclone config into the container via `--bind ~/.config/rclone:/root/.config/rclone:ro`
- At the end of the job body, resubmits itself with `sbatch "$0"` to create the self-resubmitting chain
- SIF path: `/scratch/project_465003209/mcgowank/whisper-sync.sif`

**`3-sync/setup.md` — One-time setup guide**
- Steps to create a GCP project and enable the Drive API
- Steps to create OAuth2 credentials (Desktop app type) in GCP Console
- `rclone config` walkthrough to generate `rclone.conf` with Google Drive remote named `gdrive`
- `chmod 600 ~/.config/rclone/rclone.conf` instruction
- Steps to copy `rclone.conf` from local machine to LUMI HPC via `scp`
- `docker build` and local test instructions
- `singularity build whisper-sync.sif docker-daemon://whisper-sync:latest` conversion command
- `scp` command to upload SIF to LUMI scratch
- Notes on token refresh lifetime
- Section on swapping to GCS or S3: update rclone remote type and environment variables only

### Interfaces

- `sync.sh` reads/writes `/workspace/logs/sync-manifest.txt` — one absolute file path per line, newest entries appended at the bottom
- `sync.sh` environment variables:
  - `RCLONE_REMOTE` — remote name as defined in rclone.conf (default: `gdrive`)
  - `DRIVE_INPUT` — Drive source path (default: `gdrive:whisper-sync/input`)
  - `DRIVE_OUTPUT` — Drive destination path (default: `gdrive:whisper-sync/output`)
  - `WORKSPACE` — mount point inside container (default: `/workspace`)
- rclone config mounted read-only into container at `/root/.config/rclone/rclone.conf`
- Project root always bound to `/workspace` — consistent with all other HPC scripts in the repo

### Architectural Decisions

- **Docker image as the unit of deployment:** Packages rclone and the sync script together. Eliminates "rclone not available on compute node" as an issue. Testable locally before touching HPC.
- **Docker → SIF conversion:** `singularity build` converts the Docker image to a SIF. No modifications to image contents. LUMI runs the SIF via `singularity exec`, consistent with the existing `whisper-hpc.sif` pattern.
- **Two separate one-way syncs, not bidirectional:** Drive `input/` → HPC and HPC → Drive `output/` are independent operations with no shared directory. Eliminates conflict resolution entirely.
- **Manifest-only, no auto-submit:** The sync writes a manifest but does not call `sbatch`. Inference job submission remains a deliberate manual step to protect LUMI project allocation.
- **Self-resubmitting SLURM job, not cron:** Required by LUMI policy (no user crontab on login nodes). The job resubmits itself at the end of each run.
- **rclone config mounted read-only at runtime:** The OAuth2 refresh token never baked into the image. The same image runs locally (with a test config) and on HPC (with the real token) — credentials are injected at container start via bind mount.
- **rclone as abstraction layer:** All cloud interaction goes through rclone. Switching cloud provider = updating `~/.config/rclone/rclone.conf` and two environment variables. No Dockerfile or script changes.
- **OAuth2 refresh token for personal Google account:** Service account approach deferred until a Google Workspace account is available. Token stored at `~/.config/rclone/rclone.conf` with `chmod 600`.
- **`/workspace` as container mount point:** Consistent with all existing Singularity scripts in the repo.
- **`logs/` directory reused:** Consistent with existing training and inference log conventions.

## Testing Decisions

A good test validates external behaviour — what the module produces or changes — not how it achieves it internally. Tests should not assert on rclone internals or SLURM scheduler behaviour; they should assert on the state of the filesystem and manifest after a sync run.

**Local Docker test (`3-sync/docker/test-local.sh`) is the primary test surface:**
- Uses `rclone local:` remote to simulate Google Drive with a local temp directory — no cloud credentials needed
- Mounts local `sync/` and `logs/` directories into the container
- Asserts that new files in the simulated source appear in `sync/input/` after a run
- Asserts that files in `sync/output/` appear in the simulated Drive output directory
- Asserts that `logs/sync-manifest.txt` contains the newly arrived file paths
- Asserts that a second run with no new files does not append duplicate entries to the manifest
- Asserts idempotency: running twice with the same source state produces the same manifest

**`3-sync/sync.sh` is independently testable** by running the container with a local remote and inspecting outputs — no SLURM or HPC access required.

The SLURM submission script (`sync-sbatch.sh`) is not unit-tested — its correctness is validated by submitting to LUMI and observing job queue behaviour.

There are no existing automated tests in the repo to use as prior art; `2-inference/test_infer.py` is the closest example and tests the `transcribe()` function in isolation with a real audio file.

## Out of Scope

- Auto-submission of SLURM inference jobs when new files arrive (deferred; manual manifest review is the intended workflow)
- Health-check / watchdog job that detects and restarts a broken self-resubmitting chain (deferred to v2)
- Event-driven sync via GCS Pub/Sub or Drive webhooks (polling is sufficient for the current use case)
- Encryption of files in transit beyond HTTPS (rclone uses TLS to all cloud endpoints by default)
- File deduplication or duplicate detection beyond rclone's size+modtime check
- Automatic cleanup of HPC scratch files after processing (scratch purge policy handles this externally)
- Google Workspace service account authentication (deferred until org account is available)
- Multi-user or multi-project support
- Video transcoding or pre-processing before inference
- Pushing the Docker image to a public registry (local build + SIF conversion is sufficient)

## Further Notes

- The self-resubmitting chain will stop if the SLURM job fails. The sync script should exit non-zero on rclone errors so the failure is visible in SLURM logs, but the `sync-sbatch.sh` job body should resubmit regardless of exit code so the polling chain is never silently broken.
- LUMI's `small` partition has a maximum wall time; confirm `--time=00:10:00` is within the limit before deploying.
- Google Drive API has a default rate limit of 10,000 requests per 100 seconds per user. A 5-minute polling interval is well within this limit.
- The two Drive folders (`whisper-sync/input` and `whisper-sync/output`) must be created manually in Drive before the first sync run. rclone will not create top-level Drive folders automatically.
- `singularity build` from a local Docker daemon requires Singularity (or Apptainer) installed locally. On macOS, this typically means running inside a Linux VM or using the Apptainer GitHub release binary via Lima/Colima.
- The rclone config bind mount (`--bind ~/.config/rclone:/root/.config/rclone:ro`) must use the correct host path. On LUMI, this is `~/.config/rclone`. Verify the path is accessible from the compute node's view of the filesystem.
