## Parent PRD

`prd/11-sop/prd.md`

## What to build

Add the SOP stage Python dependencies to `requirements.txt` so they are included in `whisper-hpc.sif` when it is next rebuilt. The SOP stage (`11-sop/sop.py`) runs inside the existing Singularity environment as part of `pipeline.py` — no separate image is needed.

## Acceptance criteria

- [ ] `requirements.txt` includes `xhtml2pdf` and `markdown`
- [ ] `whisper-hpc.sif` is rebuilt and the new SIF is deployed to scratch alongside the old one
- [ ] Running `pipeline.py` with `sop.enabled: true` on HPC produces `.sop.md` and `.sop.pdf` without import errors

## Replaces

- `issues/wont-do/073-sop-hpc-deployment.md`
