## Parent PRD

`issues/prd-sop-to-teleprompter.md`

## What to build

Package `teleprompter.py` for Docker. Add `11-sop/docker/Dockerfile` and `11-sop/docker/run-teleprompter.sh`. Verify end-to-end with a sample SOP file inside the container.

Reuses the existing whisper-hpc dependency set — no new base image required.

## Acceptance criteria

- [ ] `11-sop/docker/Dockerfile` builds successfully
- [ ] `11-sop/docker/run-teleprompter.sh` runs `teleprompter.py` inside the container against a sample SOP
- [ ] Output `.teleprompter.md` and `.teleprompter.review.md` are written to the mounted results volume
- [ ] Container exits cleanly with code 0 on success

## Blocked by

- `issues/002-teleprompter-core-local.md`

## User stories addressed

- Stage 2: Docker delivery (Delivery Stages section of PRD)
