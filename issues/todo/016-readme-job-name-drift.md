## Parent PRD

`prd/task-2-company-brain/prd.md`

## Status: mostly resolved by PR #9 (`75f26b0`, "task-2-part-9-readmes")

**Remaining work is the regression guard only.** The documentation drift this issue described has been fixed. Verify the fixed state, then close.

## What was wrong

`README.md` documented three SLURM job names that did not exist. The actual `#SBATCH --job-name` values differed:

| README said | Actual | Defined in |
|---|---|---|
| `A-ollama` | `B-ollama` | `3-analyze/hpc/2-ollama-serve-sbatch.sh:18` |
| `B-sync` | `C-sync` | `4-file-sync/hpc/sync-sbatch.sh:18` |
| `C-poll` | `Z-poll` | `pipeline-hpc-poll.sh:17` |

This was actively harmful, because `restart-services-sbatch.sh:35` cancels services *by name*:

```bash
scancel --name="$job_name" --user="$USER"
```

A name mismatch means a service is not restarted. The README's sample `squeue` output was also wrong, so an operator following setup instructions would be watching for job names that never appear.

## What PR #9 fixed

Verified against `75f26b0`:

- [x] No `A-ollama`, `B-sync`, or `C-poll` references remain in any `.md` file
- [x] A job-name reference table exists under "Automated HPC Pipeline (LUMI)" listing all eight services plus the array job, each mapped to its script
- [x] The stale sample `squeue` output was removed rather than left to rot
- [x] The letter-prefixed naming scheme is now documented by the table's ordering
- [x] `A-restart` is described as the supervisor that resubmits all services every 12 h
- [x] Monitoring commands are annotated with the correct job names (`tail -f logs/poll-slurm-<jobid>.out  # Z-poll`, etc.)
- [x] Component READMEs were updated in the same PR and carry no stale names

## What remains

Add an automated check so this cannot drift again. The drift happened because job names live in `#SBATCH` directives in ten separate scripts while the documentation restates them by hand — nothing enforces agreement.

- Add a test (BATS, alongside `tests/shell.bats`) that extracts every `#SBATCH --job-name=` value from `**/hpc/*.sh` and the root `pipeline-hpc-*.sh`, and asserts each appears in `README.md`.
- Assert the reverse direction too: every job name mentioned in `README.md` must exist as a real `#SBATCH --job-name`, so a typo in the docs fails the build.
- Wire it into the existing `make test` target.

## Acceptance criteria

- [ ] A test extracts all `#SBATCH --job-name` values from the sbatch scripts
- [ ] The test fails if a job name in the scripts is missing from `README.md`
- [ ] The test fails if `README.md` mentions a job name that no script defines
- [ ] The test runs as part of `make test`
- [ ] `make test` passes on the current (post-PR #9) documentation
- [ ] Adding a new service job without documenting it fails the test

## Blocked by

- None - can start immediately

## User stories addressed

- The README cannot silently drift from the actual SLURM job names again.
- `restart-services-sbatch.sh` name-based cancellation cannot break because a service was renamed without updating the docs.
