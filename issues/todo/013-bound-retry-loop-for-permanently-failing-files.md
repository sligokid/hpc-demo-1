## Parent PRD

`prd/task-2-company-brain/prd.md`

## Problem

The README carries a note anticipating exactly the failure that has now occurred. PR #9 reworded it as a "Known issue" at `README.md:254`:

> **Known issue:** There is a race condition between Z-poll and running pipeline tasks — duplicate jobs can be submitted if a file has not finished processing before the next poll cycle. This is relatively harmless (the `.done` file guards against double-indexing) but could waste GPU resources if a job stalls.

The reworded version is **less accurate than the one it replaced**. The original said the risk was a runaway job; the new text calls it "relatively harmless" on the grounds that `.done` guards against double-indexing. That reasoning only covers *transient* failures. A file that never succeeds never writes `.done`, so the guard never engages and the resubmission is unbounded — which is what actually happened.

The poison pill is not theoretical. It is currently running.

**452 of 702 array tasks have failed at inference**, and the failures are concentrated in two files that will never succeed:

| File | Attempts | Outcome |
|---|---|---|
| `sync/input/en/firedrill vid.mp4` | 226 | `INFER ERROR — ` (empty) |
| `sync/input/en/Workplace Learning Summit - Panel Full Talk.mp4` | 226 | `INFER ERROR — float division by zero` |

Zero of those 452 attempts succeeded. The loop works like this:

1. `pipeline-hpc-poll.sh` (`Z-poll`) rescans every 10 minutes and calls `pipeline-hpc-submit.sh`.
2. `find_pending` (`pipeline.py:113-127`) skips a file only if a `.done` sidecar exists.
3. On failure, `pipeline.py:217-220` does `errors += 1; continue` — skipping `done_flag.touch()` at `pipeline.py:272`.
4. No sidecar is written, so the next poll resubmits the same file. Forever.

Two separate defects combine here. The root causes are in `issues/011-no-audio-track-produces-empty-inference-failure.md` and `issues/012-float-division-by-zero-in-inference.md` — but **fixing only those leaves the loop intact**, so the next permanently-unprocessable file (a corrupt upload, a 10-hour recording, a DRM file) starts burning a GPU slot every 10 minutes with no bound.

## What to build

Bound the retry behaviour so a permanently-failing file cannot consume GPU resources indefinitely, and make the failure visible to a human instead of silent.

Add a retry-bounded skip to the done-flag protocol:

- On stage failure, write a `.failed` sidecar next to the input file recording the stage, exception type, message, attempt count, and ISO timestamp.
- `find_pending` skips files with a `.failed` sidecar, the same way it skips `.done`.
- The retry budget is configurable via `pipeline.yaml` (start at 3 attempts). Once exceeded, the file is skipped permanently and logged as permanently failed.
- A failing file is removed from the retry set on a *transient* failure only if the error class is recognised as transient (e.g. a service endpoint that was down). Everything else is treated as permanent on first failure, because the cost of a missed retry is far lower than the cost of an unbounded loop.

Make the failure loud:

- `pipeline.py` prints a clear `PERMANENTLY FAILED` line with the file path and reason when it writes a `.failed` sidecar.
- `pipeline-hpc-poll.sh` surfaces the count of permanently-failed files in its cycle log, so `tail -f logs/poll-slurm-<jobid>.out` shows a running total rather than requiring a manual `find`.
- Correct the "Known issue" note at `README.md:254`. It currently calls the race "relatively harmless", which is only true for transient failures — a permanently-failing file bypasses the `.done` guard entirely. Once this issue lands, replace the note with a description of the `.failed` convention, or remove it.
- Document the `.failed` convention and the manual recovery path (delete the sidecar to retry) in `4-file-sync/README.md`.

This is deliberately independent of fixing the two inference bugs — it is the guardrail that stops the *next* bad file from doing this.

## Acceptance criteria

- [ ] A stage failure writes a `.failed` sidecar containing stage, exception type, message, attempt count, and timestamp
- [ ] `find_pending` skips files carrying a `.failed` sidecar
- [ ] Retry budget is configurable in `pipeline.yaml` and defaults to 3
- [ ] A permanently-failing file is submitted at most `retry_budget` times, then never again
- [ ] `pipeline.py` prints an explicit `PERMANENTLY FAILED` message with the file path
- [ ] `Z-poll` logs a running count of permanently-failed files each cycle
- [ ] The "Known issue" note at `README.md:254` is corrected — it no longer describes an unbounded retry as "relatively harmless"
- [ ] The `.failed` convention and manual recovery procedure are documented in `4-file-sync/README.md`
- [ ] Deleting a `.failed` sidecar causes the file to be retried on the next poll
- [ ] The two currently-stuck files stop being resubmitted once this ships (their `.failed` sidecars may be written manually to unblock the queue immediately)

## Blocked by

- None - can start immediately. Can land before or independently of the two inference bug fixes.

## Related

- `issues/018-correct-false-sync-manifest-claim-in-readme.md` — the poller's re-glob of `sync/input/` is the mechanism that makes this loop possible, and PR #9 documented it incorrectly. Worth fixing together so the docs and the fix agree.

## User stories addressed

- The HPC GPU budget is not consumed by files that cannot succeed, regardless of what those files are.
- An operator watching the poller log can see that files have permanently failed, rather than discovering it from an ever-growing failure count.
- Removes the documented risk of a runaway pipeline job — and corrects a README note that currently understates it.
