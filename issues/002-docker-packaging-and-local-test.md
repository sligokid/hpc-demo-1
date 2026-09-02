## Parent PRD

`issues/prd.md`

## What to build

Package the sync script into a Docker image and write a local test runner that validates the full sync cycle on a developer laptop — no cloud credentials, no HPC access required.

Deliver two files:
- `3-sync/Dockerfile` — based on `rclone/rclone:latest`, copies `sync.sh` in as the entrypoint
- `3-sync/docker/test-local.sh` — builds the image, runs it with a `local:` mock remote, and asserts correct behaviour

The rclone config is never baked into the image — it is injected at container start via bind mount. This means the same image works locally (with a test config) and on HPC (with the real OAuth2 token).

See the Modules and Architectural Decisions sections of the parent PRD for the full contract.

## Acceptance criteria

- [ ] `docker build -t whisper-sync 3-sync/` succeeds with no errors
- [ ] Running `3-sync/docker/test-local.sh` completes without errors
- [ ] After the test run, a test audio file placed in the mock input source appears in the local `sync/input/` mount
- [ ] After the test run, a file placed in the local `sync/output/` mount appears in the mock output destination
- [ ] `logs/sync-manifest.txt` contains the path of the newly arrived input file
- [ ] A second run of `test-local.sh` with no new files does not add duplicate manifest entries
- [ ] The image contains no rclone credentials — config is bind-mounted at runtime
- [ ] Image builds on macOS (Apple Silicon) and produces a linux/amd64 image suitable for SIF conversion

## Blocked by

- Blocked by `issues/001-core-sync-script.md`

## User stories addressed

- User story 20 (sync packaged as a Docker image)
- User story 21 (full sync cycle testable locally with Docker and mock remote)
- User story 22 (Docker image convertible to SIF — image structure confirmed correct here)
