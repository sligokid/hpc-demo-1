# PRD 01: Stop the Bleeding — Failure Semantics and Silent Data Loss

**Parent PRD:** `prd/task-2-company-brain/prd.md`
**Source:** Codebase review, 2026-09-29. All `file:line` citations were verified against the working tree on that date and will drift — re-verify before acting on any single line.
**Pass:** 1 of 4. Companions: [02 Reclaim the Allocation](prd-02-reclaim-allocation.md) · [03 Correctness](prd-03-correctness.md) · [04 Trustworthiness](prd-04-trustworthiness.md)
**Shipping recommendation:** isolated PR. This pass changes failure semantics, which is the kind of change you want revertable on its own.

---

## Problem Statement

The pipeline processes a file through five stages — infer, analyze, sentiment, embed, index — and then writes a `.done` sidecar next to the input to mark it processed. A reviewer, and the operator watching `squeue`, both have good reason to believe that if a file is marked done, its vectors are in Qdrant and it is searchable. That is not true. A file can be transcribed, fail to reach the embedding server, get flagged `.done` anyway, and never be retried. Its vectors are gone permanently.

Worse, the run reports success. The orchestrator computes its success count from a variable that only two of the five stages increment, so a run in which every single file failed at the embed stage prints `57/57 succeeded, 0 failed` and exits zero. There is no signal — not in stdout, not in the exit code, not in the log — that anything went wrong. The failure mode and the success mode are byte-identical from the outside.

The same class of problem exists in the HPC service layer, where the failure modes are worse because they cost eight hours of GPU allocation and can take up to twelve hours to notice:

- The restart cycle submits the poller with `--dependency=after:`, which in Slurm means *after those jobs complete*. The three services it depends on are eight-hour daemons. So the poller waits roughly eight hours, then starts against three services that died at their walltime.
- If any of those three jobs exits non-zero, `afterok` is never satisfied. The poller sits in the queue indefinitely. Nothing reports the failure. The only reason the system ever recovers is that a separate twelve-hour restart cycle eventually cancels it by name.
- Consumers check that an endpoint file *exists*, never that the service behind it is *alive*. And because `scancel` sends SIGTERM — which bash does not convert into an `EXIT` trap — cancelling a service leaves its endpoint file behind pointing at a terminated node. The next consumer reads that dead address and starts anyway.
- The self-resubmitting chains install `trap ... EXIT` handlers that call `sbatch` on themselves. Cancelling those jobs sends SIGTERM, the trap never fires, and the chain survives cancellation. The documented stop procedure does not work.
- `reset-qdrant.sh` runs `scancel --me`, which cancels *every* job the user owns, contradicting its own header comment.

From an operator's seat, the system appears to be working. It is not, and there is no cheap way to find out.

---

## Solution

Make failure loud, bounded, and correctly attributed — and make every destructive action target only what it claims to target.

Five changes, in dependency order:

1. **`analyze.py` raises instead of exiting.** The module is imported by the orchestrator, so calling `sys.exit()` from inside it terminates the orchestrator, not the subprocess. `SystemExit` derives from `BaseException`, so the orchestrator's `except Exception` does not catch it. Every Ollama failure — connection refused, HTTP 500, malformed JSON, empty transcript — currently kills the whole run mid-inbox and abandons every remaining file with no summary printed. Convert the four `sys.exit(1)` call sites to raised exceptions and let the orchestrator decide.

2. **`.done` is conditional on every enabled stage succeeding.** If sentiment, embed, index, or metadata fails for a file, that file does not get its sidecar. The next poll cycle picks it up and retries it. The success count becomes the number of files that reached the end, not `total - errors`. This is the single most important change in the pass: it converts silent permanent data loss into visible, self-healing retry.

3. **Give analyze a timeout.** A hung Ollama currently blocks until the SLURM walltime is exhausted, holding a node for two hours to produce nothing. The orchestrator's own HTTP calls all carry timeouts (600s / 120s / 30s); analyze is the only caller that does not.

4. **Stop using `--dependency=after:` for services that are supposed to be running.** The poller must start *alongside* the services, not after them. Slurm has no "after this job starts" dependency type, so the correct approach is to drop the dependency entirely and let the existing fail-fast endpoint preflight in the array script handle the not-ready case. Add a liveness probe so a stale endpoint file is rejected rather than trusted, and make the chains actually stoppable.

5. **Scope the cancellation.** `reset-qdrant.sh` cancels by job name. The restart cycle's stop mechanism gains a sentinel the resubmit traps check, so cancelling a chain does not resurrect it.

---

## User Stories

1. As a pipeline operator, I want a file to be marked `.done` only when its vectors are actually in Qdrant, so that `.done` means what I think it means.
2. As a pipeline operator, I want a file whose embed or index stage failed to be retried on the next poll cycle, so that a transient embed-server hiccup does not permanently destroy that video's vectors.
3. As a pipeline operator, I want the run summary to reflect reality, so that `57/57 succeeded` never appears when nothing was indexed.
4. As a pipeline operator, I want a non-zero exit code when any file failed, so that my monitoring catches a bad run without parsing stdout.
5. As a pipeline operator, I want a transient Ollama connection error to fail one file and not the other fifty-six, so that one flaky service call does not abandon the rest of the inbox.
6. As a pipeline operator, I want the run to continue past a failed file and report a per-file error, so that I can triage failures from the log without re-running the whole batch.
7. As a pipeline operator, I want a hung Ollama request to time out, so that a wedged service burns a bounded amount of time rather than the full two-hour walltime.
8. As a pipeline operator, I want the poll cycle to start when the pipeline is ready rather than eight hours later, so that a freshly restarted system begins processing files immediately.
9. As a pipeline operator, I want the poller to fail visibly when its dependencies fail, so that a twelve-hour silent outage does not present as a healthy system.
10. As a pipeline operator, I want a stale endpoint file to be detected and rejected, so that a pipeline job does not spend twenty minutes of GPU time transcribing a file it will never be able to index.
11. As a pipeline operator, I want the endpoint preflight to verify the service responds and not merely that a file exists, so that "file present, process dead" is a caught error rather than a late-stage failure.
12. As a pipeline operator, I want to be able to stop the self-resubmitting chains with `scancel`, so that the documented stop procedure actually works.
13. As a pipeline operator, I want the stop procedure in the README to be the procedure I verified works, so that I can trust the runbook during an incident.
14. As a pipeline operator, I want `reset-qdrant.sh` to cancel only the Qdrant and index jobs, so that running it does not destroy an in-flight training array or pipeline run.
15. As a shared-cluster user, I want destructive scripts to never issue an unscoped cancel, so that I cannot accidentally cancel every job belonging to my account.
16. As a pipeline operator, I want cancelling a service to also clear its endpoint file, so that a cancelled service never leaves a usable-looking address behind.
17. As a pipeline operator, I want a file that takes longer than the poll interval to not be submitted twice, so that twenty minutes of GPU work is not duplicated every ten minutes.
18. As a pipeline operator, I want in-progress work to be distinguishable from pending work, so that the poller skips files already being processed.
19. As a pipeline operator, I want the same per-stage error handling in the analyze module whether it is invoked standalone or by the orchestrator, so that the two paths cannot diverge.
20. As a developer, I want `analyze.py` to be importable without terminating my process, so that I can write unit tests against it.
21. As a developer, I want the orchestrator's stage-failure logic to be unit-testable without HTTP or a GPU, so that the failure paths are covered by the suite rather than by production incidents.
22. As a developer, I want a test that fails if `.done` is written when the embed stage fails, so that this specific regression cannot come back.
23. As a reviewer, I want this PR to be independently revertable, so that a mistake in failure semantics does not require unwinding unrelated changes.
24. As a pipeline operator, I want the analyze timeout to be configurable rather than hardcoded, so that I can tune it without editing code on a running system.
25. As a pipeline operator, I want endpoint liveness checks to have a bounded timeout, so that a hung service fails the preflight quickly rather than stalling every array task.
26. As a pipeline operator, I want the restart cycle to verify its services came up before declaring success, so that a restart which silently failed is visible immediately rather than at the next cycle.
27. As a pipeline operator, I want a clear error naming the specific missing or dead dependency, so that I know which service to restart without cross-referencing three different scripts.
28. As a maintainer, I want the stop/resubmit sentinel mechanism documented in one place, so that adding a new self-resubmitting chain does not reintroduce this bug.

---

## Implementation Decisions

### Modules

**`pipeline.py` — stage outcome tracking**
- Introduce an explicit per-file outcome rather than a bare `errors` counter. A file that fails sentiment, embed, index, or metadata is recorded as failed, and its `.done` sidecar is *not* written.
- The `.done` write moves to the single end-of-loop success point, reached only when every enabled stage for that file completed.
- The summary line reports succeeded, failed, and skipped separately. The process exit code is non-zero when the failed count is greater than zero.
- `SKIP — no checkpoint` (`pipeline.py:206-209`) continues to count as a failure, since the operator asked for that language to be processed and it was not.
- The embed stage is additionally skipped-without-error when the segment list is empty (all timestamps were `None`, per `2-inference/infer.py:57-59`). A file with zero chunks is a legitimate no-op for indexing but must not be silently conflated with a successful index; it is reported distinctly.

**`3-analyze/analyze.py` — raise, do not exit**
- The four `sys.exit(1)` call sites (lines 53, 57, 65, 74) raise dedicated exception types instead. The CLI entrypoint catches them and maps them back to a non-zero exit, so standalone invocation behaviour is unchanged.
- Add a `timeout` to the `requests.post` call at line 46. Default 300 seconds, overridable from `pipeline.yaml`.
- Existing tests in `3-analyze/test_analyze.py` currently assert `pytest.raises(SystemExit)` at four sites. Those assertions must be updated to expect the new exception types, or PRD 01 lands with a red suite.

**`restart-services-sbatch.sh` — dependency and readiness**
- Remove the `--dependency=after:` at line 67 and the now-incorrect comment at lines 65-66.
- After submitting each service, poll its endpoint file *and probe the endpoint over HTTP* with a bounded retry loop, replacing the three fixed `sleep 120` calls at lines 39, 45, and 58. Wall-clock sleeps are a race, not a readiness gate; the services already health-check internally.
- The poller is submitted only after all three probes succeed. If any probe times out, the script exits non-zero with a message naming the service, rather than declaring the restart successful.

**Endpoint liveness — a shared probe**
- Every consumer of an endpoint file (`pipeline-hpc-sbatch.sh:33-53`, `2-index-serve-sbatch.sh:50-56`, `9-graph/hpc/graph-sbatch.sh:83-88`, `analyze-sbatch.sh:22-26`) currently tests `-f` and then `cat`s the contents. Replace with a single shared helper that (a) requires the file, (b) parses the host:port, (c) issues a bounded HTTP health request, (d) fails with a message naming which service is dead.
- The check-then-read race at `pipeline-hpc-sbatch.sh:33-53` (existence tested at 33-49, contents read at 51-53) closes as a side effect of reading once and probing the result.
- Service scripts trap `EXIT` to remove their endpoint file, which does not fire on SIGTERM. Add a `TERM` trap to the same cleanup so a cancelled service does not leave a live-looking address behind.

**Chain stop sentinel**
- `pipeline-hpc-poll.sh:40` and `4-file-sync/hpc/sync-sbatch.sh:43-45` install `trap 'sbatch --begin=... EXIT'` handlers. Because SIGTERM does not trigger `EXIT`, `scancel` by name leaves the chain running.
- Introduce a single sentinel path. The restart cycle removes the sentinel before cancelling; each resubmit trap checks for the sentinel's presence and declines to resubmit if it is absent. Cancelling a chain then genuinely stops it.
- The `|| echo "WARNING: resubmit failed"` fallback at `pipeline-hpc-poll.sh:40` is retained — a failed resubmit must remain visible, not silent.

**`reset-qdrant.sh` — scoped cancellation**
- Replace `scancel --me` (line 20) with explicit `scancel --name=<job>` for the Qdrant and index jobs only.
- The fixed `sleep 15` at line 23 is not a wait — `scancel` is asynchronous. Replace with a bounded loop that polls until the target jobs have left the queue.
- Deleting Qdrant storage under a process that may still hold it open is a race; the same loop covers it.
- The script's header currently promises it "restarts both services" while the body only cancels and deletes. Correct the header to match the body, or make the body match the header — decide and be consistent.

**Poll race on long files**
- `.done` is written only after all five stages (`pipeline.py:272`), so any file exceeding the ten-minute poll cycle is re-submitted by `pipeline-hpc-submit.sh:45`, duplicating completed GPU work every cycle.
- Write an in-progress marker when a file is claimed and remove it in a `finally` block, so the poller skips files currently being worked on. The marker is distinct from `.done` — it means "claimed", not "complete".
- This is a prerequisite for the `.done` change in the first bullet: once failed files stop being flagged done, retry becomes automatic and the poll race becomes the dominant source of duplicate work.

### Architectural decisions

- **Raise, don't exit, in library code.** `analyze.py` is imported by the orchestrator; any exit call in it is a process-level action taken from library context. This is the root cause of finding 2 and it should not recur in other stage modules.
- **`.done` means "fully processed," nothing else.** One flag, one meaning. The in-progress marker is a separate concept with a separate name, so a reader never has to reason about flag combinations.
- **Liveness over existence for service discovery.** The endpoint-file pattern is a good design and stays. What changes is that consumers verify the process answers, not just that a file is present. The endpoint file becomes a *pointer*, and the probe becomes the *check*.
- **Readiness gating belongs in the submitting script.** Slurm has no "after this job starts" dependency. Readiness is therefore something the restart script verifies itself, before submitting the poller, rather than something it delegates to the scheduler.
- **Destructive scripts name their targets.** An unscoped `scancel` is never appropriate in a shared-account environment, regardless of how convenient it is.
- **Failures are visible even when the pipeline is unattended.** This is the constraint that outranks convenience throughout this pass. Every change here trades a little convenience for a loud failure.

### Interfaces

- `pipeline.yaml` gains an `analyze.timeout_seconds` key (default 300). The existing `PIPELINE_<KEY>` env-override claim at line 2 is unimplemented — either implement it or delete the claim. That work is scheduled in PRD 04; until then, document the timeout as config-file-only.
- Analyze raises a dedicated exception per failure mode (connection refused, non-200 response, unparseable body, empty input) rather than a bare `Exception`, so the orchestrator can distinguish a retryable service outage from a permanently malformed input.
- The shared liveness probe takes a URL and a timeout and returns a boolean. It does not raise, so callers can choose their own error wording.

### Deliverables

| # | Deliverable | Description |
|---|---|---|
| 1 | `analyze.py` exception refactor | Replace 4 `sys.exit(1)` with raised exceptions; CLI maps back to non-zero exit |
| 2 | Analyze HTTP timeout | `timeout=` on the Ollama POST, configurable from `pipeline.yaml` |
| 3 | `pipeline.py` outcome tracking | Per-file success/failure state; `.done` only on full success |
| 4 | `pipeline.py` summary and exit code | Accurate counts; non-zero exit when anything failed |
| 5 | In-progress marker | Claimed-vs-complete distinction; poller skips in-flight files |
| 6 | Shared liveness probe | Bounded HTTP health check, replaces bare `-f` tests |
| 7 | Consumer migration | `pipeline-hpc-sbatch.sh`, `2-index-serve-sbatch.sh`, `graph-sbatch.sh`, `analyze-sbatch.sh` use the probe |
| 8 | Service `TERM` traps | Endpoint files removed on SIGTERM as well as normal exit |
| 9 | Restart readiness gating | Drop `--dependency=after:`; probe services; poll last |
| 10 | Chain stop sentinel | Sentinel file the resubmit traps honour |
| 11 | `reset-qdrant.sh` scoped cancel | `--name=` targets only; bounded wait replaces `sleep 15` |
| 12 | Updated analyze tests | Four `SystemExit` assertions replaced |

---

## Testing Decisions

A good test here asserts **observable outcome**: did the `.done` file appear, what did the process exit with, what did it print. It does not assert on internal control flow, and it does not require a GPU, a network, or Qdrant.

**Prior art in this repo:** `5-sentiment/test_sentiment.py` and `2-inference/test_infer.py` both use `unittest.mock.patch.object` to inject a fake dependency into a module-level function, then assert on the returned structure. `tests/shell.bats` mocks at the shell boundary with counter-driven fake binaries. Both patterns apply directly.

### The two tests this PRD exists to make possible

There is currently no test file for the orchestrator at all — 282 lines, zero coverage. Two specific cases:

1. **`.done` is not written when the embed stage fails.** Set up a pending file, stub the embed HTTP call to raise, run the pipeline, assert the `.done` sidecar does not exist and the exit code is non-zero. This test fails against the current code and is the direct regression guard for the worst bug in the repository.

2. **A `SystemExit` from analyze does not terminate the run.** With two pending files, make analyze raise the new exception type (and, separately, raise a bare `SystemExit` to prove the orchestrator is robust to it), assert the loop continues to the second file and both failures are reported. This test fails against the current code.

Additional cases: empty segment list produces a skip rather than a success; a missing checkpoint counts as a failure; a successful run writes `.done` for every file and exits zero; the summary counts match the number of pending files.

**`3-analyze/analyze.py`:** the timeout is passed to the HTTP client (assert via a mock); each raised exception type is raised for its trigger condition; the CLI still exits non-zero for each of the four original conditions, so standalone behaviour is provably unchanged.

**Bats coverage for the shell changes:** the endpoint liveness probe rejects a file pointing at a closed port and accepts one pointing at a live mock server; the resubmit trap declines to resubmit when the sentinel is present; `reset-qdrant.sh` issues `scancel --name=...` and never `scancel --me`; the restart script submits the poller only after all three probes succeed and exits non-zero when one fails.

**Not unit-tested:** actual SLURM scheduling behaviour, and real service startup. Those are validated by submitting to LUMI and watching the queue, as `prd/done/4.file-sync/prd.md` established for the sync chain.

### Note on ordering

Deliverable 5 (in-progress marker) should land with or before deliverable 3 (`.done` semantics). Once failed files stop being flagged done, the poller will begin retrying them — and without an in-progress marker, a slow retrying file is itself re-submitted every ten minutes.

---

## Out of Scope

- **Making the pipeline idempotent at the Qdrant level.** The `uuid5` point IDs already make re-indexing safe, so retries are already cheap. Not needed for correctness here.
- **Retrying failed files more than once.** One retry per poll cycle is enough; a file that fails four cycles in a row is probably not transient. Alerting on that is a monitoring concern, out of scope.
- **Circuit-breaking the services.** If Ollama is down, every array task will still fail individually. A breaker would be better but is a larger design change.
- **Correcting `reset-qdrant.sh` to actually restart services** (as its header claims). This PRD makes the body match the header by fixing the header. The larger question of whether a reset script should restart anything is deferred.
- **The GPU over-requests and resource waste.** Scheduled as PRD 02.
- **The `.done`-on-stem-collision case** (`pipeline.py:191`, where `a.mp3` and `a.mp4` overwrite each other's outputs). A genuine correctness bug, but not a failure-semantics one — scheduled for PRD 03.
- **Writing the orchestrator test suite in full.** This PRD requires the two regression tests named above and the supporting cases. Broad coverage of the orchestrator is scheduled in PRD 04, and the two PRDs will touch the same file.

---

## Further Notes

- **The `afterok` deadlock is the most serious finding in this pass.** If the index server's own preflight fails (its Qdrant endpoint file is absent), `afterok` on a failed job is *never* satisfied. The poller waits indefinitely, nothing reports the failure, and recovery depends on the twelve-hour restart cycle eventually cancelling it by name. This presents as a healthy system for up to twelve hours.
- **LUMI has automatic requeuing enabled on node failure.** A requeued job restarts the script body, re-arms the `EXIT` trap, and submits another poll job while the pre-failure one is still queued — producing two concurrent poll chains, each submitting overlapping pipeline arrays. Add `--no-requeue` and `--open-mode=append` to the self-resubmitting jobs. LUMI's own documentation recommends both; `append` additionally preserves the diagnostics from the failed attempt instead of truncating them.
- **The poll chain has no re-entrancy guard.** Nothing stops a second operator from running `sbatch pipeline-hpc-poll.sh` twice. Two chains then submit overlapping arrays. A lock or a single-instance check is the natural companion to the sentinel from this PRD.
- **`sbatch --dependency` placement.** `pipeline-hpc-submit.sh:67` places `--parsable` after the script name. This works only because glibc's `getopt_long` permutes arguments. Moving it before the script path is a one-line robustness fix, harmless to include.
- **The manifest race.** `pipeline-hpc-submit.sh` passes the manifest path to the array job, which may read it hours later if held by a dependency. Anything that rewrites or removes it in the interim changes the job's file assignment. This PRD removes the dependency that caused the hours-long delay, which substantially reduces the exposure, but does not eliminate it.
- **This PRD changes behaviour that a demo may currently rely on.** If anything downstream was written to tolerate `.done` appearing despite embed failure, that will now correctly surface as a retry. That is the intent, but it will look like a behaviour change on first run.
- **Verify `logs/` exists at submit time.** Every `#SBATCH --output=logs/...` directive requires it, and `mkdir -p` inside the script body runs too late — `slurmd` opens the file before the body starts. This affects the poller, which the README's launch sequence submits first. It is a pre-existing footgun rather than a failure-semantics issue, so it is scheduled for PRD 04, but it will surface the first time this PRD's changes are tested on a fresh clone.
