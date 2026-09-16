## Parent PRD

`prd/4.extract/hpc/prd.md`

## What to build

A `bats` test suite covering the observable behaviour of the three new shell scripts: `ollama-serve.sh`, `ollama-pull.sh`, and `analyze-batch.sh`. Tests mock external commands (`curl`, `ollama`, SLURM env vars) at the shell boundary and assert correct exit codes, file creation/deletion, and error messages.

See PRD §Testing Decisions.

## Acceptance criteria

- [ ] `ollama-serve.sh` health-check loop: mock `curl` to return non-200 twice then 200; assert endpoint file is written only after the successful response
- [ ] `ollama-serve.sh` cleanup trap: send `SIGTERM` to the script; assert the endpoint discovery file is removed
- [ ] `analyze-batch.sh` missing discovery file: invoke without a discovery file present; assert exit code is non-zero and stderr contains a descriptive error
- [ ] `ollama-pull.sh` successful pull: mock `ollama list` to include the expected model name; assert exit code 0
- [ ] `ollama-pull.sh` failed pull: mock `ollama list` to return empty/absent model; assert exit code non-zero
- [ ] Tests are runnable locally with `bats tests/`
- [ ] CI or Makefile target documented for running the bats suite

## Blocked by

- Blocked by `prd/4.extract/hpc/issues/001-ollama-serve.md`
- Blocked by `prd/4.extract/hpc/issues/002-ollama-pull.md`
- Blocked by `prd/4.extract/hpc/issues/003-analyze-batch.md`

## User stories addressed

- Testing decisions: health-check loop, cleanup trap, missing discovery file, pull success/failure
