## Parent PRD

`prd/4.extract/hpc/prd.md`

## What to build

Add a README section documenting the end-to-end HPC workflow: build the Ollama Singularity image, pull model weights, start the persistent service, submit the analysis array job, and use the interactive wrapper. Include the one-liner chained submission command that runs the full pipeline unattended.

See PRD §User Stories 25, 30.

## Acceptance criteria

- [ ] README covers: `singularity pull` to build `ollama.sif`
- [ ] README covers: `ollama-pull.sh` one-time model pull step
- [ ] README covers: `sbatch ollama-serve.sh` to start the persistent service
- [ ] README covers: `sbatch --dependency=after:<jobid> analyze-batch.sh` for coordinated submission
- [ ] README covers: `./analyze-on-gpu.sh transcripts/foo.txt` for interactive single-transcript use
- [ ] README includes the single command that chains transcription, service start, and batch analysis for unattended overnight runs
- [ ] Directory layout (`transcripts/`, `metadata/`, `logs/`, scratch paths) is shown
- [ ] Added to the existing README without replacing existing content

## Blocked by

- Blocked by `prd/4.extract/hpc/issues/001-ollama-serve.md`
- Blocked by `prd/4.extract/hpc/issues/002-ollama-pull.md`
- Blocked by `prd/4.extract/hpc/issues/003-analyze-batch.md`
- Blocked by `prd/4.extract/hpc/issues/004-analyze-on-gpu.md`
- Blocked by `prd/4.extract/hpc/issues/005-shell-tests.md`

## User stories addressed

- User story 25
- User story 30
