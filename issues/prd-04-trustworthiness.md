# PRD 04: Trustworthiness — Tests, CI, Dependencies, and Honest Documentation

**Parent PRD:** `prd/task-2-company-brain/prd.md`
**Source:** Codebase review, 2026-09-29. All `file:line` citations were verified against the working tree on that date and will drift — re-verify before acting on any single line.
**Pass:** 4 of 4. Companions: [01 Stop the Bleeding](prd-01-stop-the-bleeding.md) · [02 Reclaim the Allocation](prd-02-reclaim-allocation.md) · [03 Correctness](prd-03-correctness.md)

---

## Problem Statement

This repository has 96 passing Python tests and 7 passing shell tests. Running `make test` executes 7 of them. There is no pytest target, and `pytest` is a declared dependency with nowhere to be invoked from a single command. Anyone who runs the documented test command gets a green result and a false sense of coverage, while the entire Python suite sits unexecuted.

The gap matters more than a normal coverage gap because the orchestrator — 282 lines, the highest blast-radius file in the system, and the source of the two worst bugs found in review — has no test file at all. Neither `pipeline.py` defect was caught, and neither could have been: there is nothing to catch it.

Some existing tests actively protect the wrong behaviour. The sentiment "majority label wins" test names a scenario it never creates, because the mock is configured per-call while the code makes one call with all inputs — it passes for the wrong reason. The analyze tests assert `pytest.raises(SystemExit)` at four sites, which locks in the exact behaviour that lets a single Ollama error terminate the orchestrator. A fragile assertion in the graph tests checks for a JavaScript identifier in a template, coupling the test to a variable name and asserting nothing about behaviour.

**The documentation is worse than absent — it is confidently wrong.** `CLAUDE.md` instructs the reader to run four scripts that do not exist, states that training loads Common Voice when it loads FLEURS, and tells a developer extending the language list to add to a constant that does not exist — following that instruction produces a `NameError`. It is loaded automatically into every assistant session working in this repository, so its errors are actively propagated rather than merely misleading. `README.md` shows a stale job-naming scheme from a previous revision, omits two of the five required container images from its prerequisites, and recommends a quick-start script that fails on its first command. `pipeline.yaml` documents an environment-variable override system that was never implemented.

**Dependencies do not match the code.** `pipeline.py` imports `yaml`; `pyyaml` is not in `requirements.txt`. It appears only in a service's requirements file, in a service that does not import it. A clean virtual environment can fail at `import pipeline`. `requests` is likewise undeclared, present only transitively.

**And the tree is accumulating wreckage.** Two directories left behind by a rename contain only stale bytecode and old logs, and appear in every `git status` as untracked noise. The Docker image publish script is entirely commented out, references a directory that no longer exists, and has no build line for one of the two service images — so that image has no reproducible publish path anywhere. The build context does not exclude the input media directory, so every image build ships the entire video corpus into the context.

The through-line: this is a repository where the parts that were never finished are indistinguishable from the parts that were done well. The service scripts are genuinely excellent — atomic endpoint writes, `set -euo pipefail`, bounded health checks, EXIT-trap cleanup. The documentation around them describes a system that does not exist.

---

## Solution

Make the test suite runnable as one command, actually run it, and protect the orchestrator. Add CI so none of this regresses silently. Make the documentation true. Make the dependency list complete. Delete what is dead.

Seven groups:

**A — Test entry point.** Add a Python test target and make the aggregate run both suites. A single command must execute everything.

**B — Close the coverage gap.** Write the orchestrator test suite. Fix the no-op test. Replace the assertions that lock in wrong behaviour. Remove the fragile template assertion.

**C — CI.** Run the full suite on commit. This is what stops every other item in this PRD from regressing.

**D — Documentation truth.** Rewrite `CLAUDE.md` against the actual tree. Correct `README.md`'s job names, prerequisites, and quick-start. Either implement the documented environment override in `pipeline.yaml` or delete the claim. Fix the stale cross-references in code comments and docstrings.

**E — Dependencies and packaging.** Declare what the code imports. Exclude the media corpus from the build context. Restore a build path for every published image. Add the pytest configuration that makes imports deterministic.

**F — Delete the dead.** Orphan directories, the fully commented-out script, a duplicated script pair, a root `Dockerfile` nothing references.

**G — Shell script hygiene.** Add the missing `set -euo pipefail` where its absence creates a silent failure loop. Fix the scripts that reference files that do not exist. Guard the array submission that fails when there are no files.

---

## User Stories

### Group A — Test entry point

1. As a developer, I want one command that runs every test, so that I do not choose a subset by accident.
2. As a developer, I want `make test` to include the Python tests, so that the documented command is not misleading.
3. As a developer, I want the test target to fail loudly when a suite cannot start, so that a missing dependency is not mistaken for a pass.
4. As a developer, I want test prerequisites listed, so that a fresh clone does not fail on a missing test runner.
5. As a reviewer, I want to see a test target in the Makefile, so that tests are part of the project's shape rather than folklore.

### Group B — Coverage gap

6. As a developer, I want the orchestrator to have tests, so that its failure paths are verified rather than discovered in production.
7. As a developer, I want a test for the done-flag semantics, so that the file-completion contract is enforced.
8. As a developer, I want a test for stage ordering, so that a stage cannot be silently reordered.
9. As a developer, I want a test for the error counter, so that the summary cannot lie about success.
10. As a developer, I want a test for the single-file and inbox code paths, so that both are covered.
11. As a developer, I want a test asserting a real sentiment input produces the expected label, so that the test's name matches what it verifies.
12. As a developer, I want the analyze tests to assert current intended behaviour, so that they do not freeze a bug in place.
13. As a developer, I want the graph test to assert rendered output rather than a variable name, so that renaming a variable does not break the suite.
14. As a developer, I want the training module to have tests, so that its collator and metric code is covered.
15. As a developer, I want tests for the collator's label preparation, so that that logic is verified.
16. As a developer, I want a test asserting deterministic index IDs, so that the idempotency guarantee is protected.
17. As a developer, I want the role configuration validated against the real profiles, so that configuration drift is caught.
18. As a developer, I want tests for the embed service's error paths, so that a model-load failure is caught.
19. As a developer, I want tests to import modules the same way everywhere, so that the suite does not depend on the working directory.
20. As a developer, I want bats coverage for the remaining job scripts, so that the service layer is not untested.

### Group C — CI

21. As a developer, I want tests to run on every push, so that a broken commit is caught before review.
22. As a developer, I want CI to run the shell tests too, so that the documented test command is enforced.
23. As a maintainer, I want CI failures visible without reading logs manually, so that regressions are noticed.
24. As a developer, I want CI to be fast enough to run on every commit, so that people do not skip it.

### Group D — Documentation

25. As a developer, I want every command in the documentation to reference a file that exists, so that I can run what I read.
26. As a developer, I want the documentation to name the correct training dataset, so that I understand what is being trained on.
27. As a developer extending the language list, I want to be told the correct constant name, so that I do not get an error.
28. As a reader, I want the documentation to describe the current architecture, including the services it omits, so that I understand the system I am deploying.
29. As a reader, I want the endpoint-file convention documented, so that I can diagnose a service-discovery failure.
30. As a reader, I want the documented job names to match reality, so that my `squeue` output makes sense.
31. As a reader, I want the prerequisites to list every required container image, so that a fresh deployment starts.
32. As a reader, I want the quick-start command to work, so that my first attempt is not a failure.
33. As a reader, I want the stop procedure to be one that works, so that I can follow it in an incident.
34. As a developer, I want the environment override either implemented or removed from the docs, so that I do not rely on a feature that does not exist.
35. As a developer, I want code comments to point at files that exist, so that a cross-reference is useful.
36. As a developer, I want the file-sync loop to have the strict-mode treatment the other scripts have, so that a failed sync does not loop forever in silence.
37. As an operator, I want the sync job to fail visibly when its credentials are missing, so that a permanent failure is not reported as a healthy loop.

### Group E — Dependencies and packaging

38. As a developer setting up a fresh environment, I want the dependency list to be complete, so that the import of the orchestrator succeeds.
39. As a developer, I want redundant dependencies removed, so that the list is honest about what is needed.
40. As a developer, I want the image build to exclude the media corpus, so that builds are fast and small.
41. As a developer, I want every published image to have a build command, so that I can rebuild it.
42. As a developer, I want the test configuration to be explicit, so that imports work from any working directory.
43. As a developer, I want the container Python versions aligned, so that behaviour does not drift between environments.
44. As a developer, I want the container to be runnable, so that a built image can be started and inspected.

### Group F — Delete the dead

45. As a developer, I want unused directories removed, so that the tree reflects what exists.
46. As a developer, I want stale bytecode removed, so that it cannot be imported by accident.
47. As a developer, I want a dead script with no active lines removed, so that it is not mistaken for a working one.
48. As a developer, I want the duplicated query script resolved, so that I know which one to run.
49. As a developer, I want the unreferenced root container file resolved, so that I know which one to build.
50. As a reviewer, I want a clean working tree, so that untracked noise does not hide a real change.

### Group G — Shell hygiene

51. As a developer, I want scripts to use strict mode consistently, so that failures are not silently ignored.
52. As a developer, I want a script to guard against submitting an empty array, so that it does not fail with a scheduler error.
53. As a developer, I want the SIF pull script to use strict mode and a shebang, so that a failed pull is not reported as success.
54. As an operator, I want the SIF pull cache on appropriate storage, so that pulling large images does not exhaust login-node memory.
55. As a developer, I want the SIF pull script to work from any directory, so that images land in the right place.
56. As a developer, I want the local Docker restart script to report a missing service rather than aborting silently, so that I know what went wrong.
57. As a developer, I want the local restart script to skip an already-present model, so that a restart does not re-download it.
58. As a developer, I want the sync manifest check to scale, so that a large inbox does not spawn a process per file.

---

## Implementation Decisions

### Group A — Test entry point

**`Makefile` (9 lines).** Two targets, both bats, with the aggregate aliasing only the shell suite. Add a Python target covering the co-located `test_*.py` files, and make the aggregate depend on both. Two files already document per-file pytest invocations; the target should discover all of them rather than hardcode a list that drifts.

Make the targets fail if a runner is missing, so a fresh clone produces "install pytest" rather than a silent skip. Document both prerequisites — bats and pytest — in the target comments, as the current target does for bats.

### Group B — Coverage gap

**Orchestrator tests.** The largest gap in the repository. The orchestrator lazily imports its stage modules through a small helper (`pipeline.py:44-97`) precisely so that stages can be stubbed. Tests should inject fakes at that seam rather than patching HTTP directly — the seam already exists for this purpose.

Cover: the pending-file scan and its filters; the done-flag contract, including the case where a stage fails (PRD 01 defines the expected behaviour); stage ordering; the error accounting and the process exit code; the single-file path versus the whole-inbox path; the configuration toggles for each stage; the stem-collision case that PRD 03 fixes.

**Tests that currently protect wrong behaviour.**

- `5-sentiment/test_sentiment.py:115-130` — a no-op. The mock returns one item per call, but the code makes a single call with all texts, so exactly one chunk is classified and the majority path never runs. Rewrite it to actually drive the majority logic, and confirm it fails when the majority logic is broken.
- `3-analyze/test_analyze.py` — four `pytest.raises(SystemExit)` assertions. These lock in the behaviour PRD 01 changes. They must be updated in PRD 01; this pass verifies none were left behind.
- `9-graph/test_graph.py:176` — asserts a JavaScript identifier is present in the template. Rename the variable and the test breaks; break the rendering and it passes. Assert on rendered content.

**Coverage that does not exist at all.** The training module has no tests — the collator's label preparation and the metric computation are both unverified. The role configuration and the real user profiles are never validated together, so a tag renamed in one file and not the other is invisible; the current playlist test uses an inline fixture rather than the shipped configuration, which is precisely why drift is possible. The embed service's error paths are untested, including the case where a length-mismatched vector is returned and the case where the model is `None`.

**Import hygiene.** Five test files manipulate `sys.path` themselves; two rely on pytest's implicit rootdir insertion. It works today by accident and would break under a different import mode or a different working directory. Add pytest configuration that makes it explicit and remove the per-file manipulation.

**Shell coverage.** Bats currently covers three of the three-analyze scripts. Eight other job scripts have no coverage, including the three service scripts that share the most boilerplate — precisely the ones where PRD 01 and PRD 02 make changes. The mocking pattern in the existing bats file (a counter-driven fake binary) is the right one and should be reused.

### Group C — CI

Add a workflow that runs the full suite — both Python and shell — on push and pull request. No repository automation exists today. Keep it fast: the Python tests are unit tests with mocked dependencies, so the suite should run in seconds. GPU and HPC-dependent paths are not tested in CI and cannot be; that is what the existing local and HPC verification steps are for.

### Group D — Documentation truth

**`CLAUDE.md` is the priority.** It is loaded into every assistant session in this repository, so its errors are propagated rather than merely read. It documents four files that do not exist, names the wrong training dataset, and instructs the reader to extend a constant that does not exist. Rewrite it against the actual tree. It also omits the majority of the production surface — the configuration file, the three pipeline scripts, the restart and reset scripts, the service stages, and the endpoint-file convention that underpins the whole HPC deployment.

**`README.md`.** The job names in the architecture diagram and the sample `squeue` output are from a previous revision. The prerequisites list three of the five required container images. The launch sequence omits creating the logs directory, which every submission requires. The quick-start script it recommends fails on its first command. One language's checkpoint path is wrong. All of these are small edits with a disproportionate effect on whether a new operator can deploy the system.

**`pipeline.yaml`.** The header documents an environment-variable override for every key. It is not implemented; only two service URLs are overridable. Either implement it or delete the claim. Deleting is honest and cheap; implementing it is a genuine feature that belongs in configuration work.

**Stale cross-references in code.** A comment in the analyze module points at an issue file that has since been renumbered. A sentiment docstring instructs the reader to run the module from a directory that was renamed two stages ago. The orchestrator's docstring names an inference module it does not use, and describes an output location the configuration has since changed. A comment in the embed server references a service endpoint that moved. These are cheap to fix and actively harmful when followed.

### Group E — Dependencies and packaging

**`requirements.txt`.** Add the YAML library the orchestrator and the playlist generator both import — it appears only in a service's requirements file, in a service that does not import it, so a clean environment can fail at import. Add `requests`, used directly by the orchestrator and the analyze module but present only transitively. Remove the duplicate word-error-rate dependency, which the evaluation library already pulls in.

**`.dockerignore`.** Exclude the sync directory. The build context currently includes the entire input media corpus — dozens of video files — on every image build. The existing ignore list is otherwise sensible and correctly excludes checkpoints, logs, and the virtual environment.

**Image build paths.** The publish script is entirely commented out, references a directory that was renamed, and has no build line for one of the two service images that Docker Compose references. Restore a working build and publish path for both service images.

**Python version drift.** Three different base versions across the image set. Align them, or document why they differ. Behavioural differences between the tested environment and the deployed environment are exactly the class of problem this pass exists to remove.

**Root `Dockerfile`.** Referenced by nothing — no compose service, no build script. Either wire it in or remove it. Its filtering approach for the accelerator wheel is a good pattern worth preserving wherever it survives.

### Group F — Delete the dead

- Two orphan directories left by a rename, containing only stale bytecode and old logs. Untracked, and visible as noise in every `git status`.
- The fully commented-out publish script, once its contents are restored under Group E.
- A pair of byte-identical query scripts where one claims to read standard input and does not. Keep one, and make it actually read standard input.
- A root container file nothing references.
- A module docstring and a commented build line that both reference the renamed directory.

Add ignore rules so the orphan directories cannot reappear from a stale run.

### Group G — Shell hygiene

**Missing strict mode.** The file-sync job is the only service-layer job without `set -euo pipefail`, and the omission is consequential: if the sync fails — missing container image, missing credentials, a transient authorisation error — the script falls off the end, the resubmit trap fires, and the chain continues. That is an infinite silent failure loop, with the error visible only in a log nobody knows to check. The image pull script has the same gap plus no shebang, so a failed pull is reported as success.

**Guard the empty array.** A wrapper that computes a file count and submits an array job produces a malformed range when the count is zero, and the failure is a scheduler error rather than a clear message.

**Cache location.** The image pull script points its cache at a memory-backed temporary directory on a login node, then pulls five multi-gigabyte images into it. That will exhaust login-node memory. Point it at scratch.

**Output path dependence.** The same script uses working-directory-relative output paths that only land in the right place when invoked from the project root — an invariant that is neither documented nor enforced, and which the documented steps contradict by using absolute paths instead.

**Local Docker restart.** One assignment under strict mode aborts the whole script silently when the container query returns nothing, instead of reporting that the service is missing. And the model pull runs unconditionally on every restart, re-downloading a multi-gigabyte model each time; the HPC equivalent already does the pre-check correctly.

**Sync manifest scaling.** The manifest check invokes a text search once per new file. For a large inbox that is one subprocess per file per cycle. Read the manifest once and match in-process.

**Credentials preflight.** The sync job binds a credentials directory into the container without checking it contains a configuration file. When absent, the container may create an empty directory owned by root, making the first failure permanent and difficult to repair. Check before binding, and warn in the documentation that the credentials contain a long-lived refresh token in plaintext on shared storage.

---

### Deliverables

| # | Deliverable | Group | Description |
|---|---|---|---|
| 1 | Python test target | A | Discovers all co-located tests |
| 2 | Aggregate runs both suites | A | `make test` executes Python and bats |
| 3 | Test runner preflight | A | Clear message when a runner is missing |
| 4 | Orchestrator test suite | B | Pending scan, done-flag contract, ordering, error accounting, both entry paths |
| 5 | Sentiment test fixed | B | Drives the majority path it claims to test |
| 6 | Analyze assertions updated | B | No `SystemExit` expectations left behind |
| 7 | Graph assertion de-coupled | B | Asserts rendered content, not a variable name |
| 8 | Training module tests | B | Collator label preparation and metric |
| 9 | Idempotency test | B | Deterministic index IDs protected |
| 10 | Config validation test | B | Role config checked against real profiles |
| 11 | Embed error-path tests | B | Length mismatch and unloaded model |
| 12 | Pytest configuration | B | Deterministic imports without per-file path manipulation |
| 13 | Bats coverage for remaining jobs | B | The service scripts this pass set changes |
| 14 | CI workflow | C | Full suite on push and pull request |
| 15 | `CLAUDE.md` rewritten | D | Against the actual tree; includes omitted subsystems |
| 16 | `README.md` corrected | D | Job names, prerequisites, launch sequence, quick-start |
| 17 | Env-override claim resolved | D | Implemented or removed from config |
| 18 | Stale cross-references fixed | D | Comments and docstrings pointing at real files |
| 19 | Missing dependencies declared | E | YAML library and HTTP client |
| 20 | Redundant dependency removed | E | Word-error-rate library already transitive |
| 21 | Build context excludes media | E | Sync directory ignored |
| 22 | Image build paths restored | E | Both service images buildable and publishable |
| 23 | Python versions aligned | E | Or the divergence documented |
| 24 | Root container file resolved | E | Wired in or removed |
| 25 | Orphan directories deleted | F | Stale bytecode and logs removed |
| 26 | Dead publish script removed | F | After its contents are restored |
| 27 | Duplicate query script resolved | F | One script that actually reads standard input |
| 28 | Ignore rules added | F | Orphans cannot reappear |
| 29 | Strict mode added | G | Sync job and image pull script |
| 30 | Empty array guarded | G | Clear message instead of a scheduler error |
| 31 | Image cache relocated | G | Scratch, not login-node memory |
| 32 | Pull script path-independent | G | Works from any directory |
| 33 | Local restart reporting fixed | G | Missing service reported, not silent abort |
| 34 | Model pull made conditional | G | Skip when already present |
| 35 | Sync manifest check scaled | G | One read, not one subprocess per file |
| 36 | Credentials preflight | G | Check before binding; document the token risk |

---

## Testing Decisions

This PRD is largely about making the existing tests trustworthy, so its testing decisions are meta — but they are the most important ones in the pass. A test that passes for the wrong reason is worse than no test, because it converts an unknown into a false certainty.

**Standard: a test must fail when the behaviour it names is broken.** For every test touched in this pass, verify this explicitly by temporarily breaking the behaviour and confirming the test goes red. This is a one-minute check that catches no-op tests, and it is how the sentiment test's flaw was found.

**A test must set up the scenario its name claims.** Where a mock is configured to return N items but the code makes one call, the test is not testing what it says. When a mock's return shape does not match how the code invokes it, that mismatch is the finding.

**Assert on content, not shape.** Several existing tests assert that a key is present or that a variable name appears in a template. Both pass whether or not the system works. New assertions check values, rendered output, and observable filesystem and process state.

**Do not assert on implementation details.** A test that breaks when a helper is renamed is a maintenance tax, not a safety net. The graph template test is the model to avoid; the orchestrator tests should exercise the public entry point and observe outputs.

**Test the configuration against the real configuration.** The playlist test's inline fixture is why role-configuration drift is currently invisible. Configuration tests must read the shipped files.

**For CI:** the suite must be fast enough that people do not skip it, which means unit tests with mocked dependencies only. GPU execution, real Qdrant, real Ollama, and anything requiring LUMI cannot run in CI and are verified by the existing local and HPC verification steps. Be explicit about which is which, so a green CI run is not mistaken for a full system verification.

**The bats additions** follow the existing pattern in the repository: mock at the shell boundary, use counter-driven fake binaries, and use `exec` where correct signal delivery matters. The two assertions most worth adding are the resource-directive guard from PRD 02 and the strict-mode guard from this group — both are cheap and catch a whole class of regression.

---

## Out of Scope

- **Rewriting the two companion PRDs' code fixes.** This pass makes the suite able to verify them; it does not perform them.
- **The orchestrator's design.** It is a 282-line procedural script that grows with each stage. Refactoring it into something more structured is a legitimate future project, but this pass only adds tests. Be aware that testing an untested procedural script often reveals that it is harder to test than expected — budget for that.
- **Removing `pyyaml` usage.** The configuration file uses YAML and two modules read it. A different format is a real option but is a separate decision from declaring the dependency.
- **Aligning the container images' contents.** Aligning the Python versions is in scope. Rebuilding the images to share a base is not.
- **Removing the foreign keys and shared runtime concerns** that `prd/done/4.file-sync/prd.md` already raised. The credentials preflight here is a precondition for that work, not a substitute for it.
- **Testing the actual ML model outputs.** Whether the fine-tuned checkpoints produce good word-error rates is measured by the training run, not by a unit test.
- **Documenting the LUMI-specific operational knowledge** that currently lives only in the review. Some of it — the requeue interaction, the per-node memory semantics, the eight-GCD topology — belongs in the repository rather than in a chat transcript. That is a documentation task worth doing once the inaccurate material is removed.
- **Licence, contribution, and changelog files.** Not currently present and not requested.

---

## Further Notes

- **`CLAUDE.md` is the single highest-leverage item in this pass per unit of effort.** It is a fifteen-minute fix, it is loaded into every assistant session in this repository, and it currently instructs the reader to run four scripts that do not exist and to edit a constant that does not exist. Everything else here is measured in hours; this one is measured in the damage it stops causing. It is listed under Group D for ordering, but consider pulling it forward as a standalone commit before the rest of this pass.
- **The Makefile is the highest-leverage bug.** One line — the aggregate target depending only on the shell suite — means 96 tests do not run when a developer follows the documented command. It is the cheapest fix in the entire four-pass review and it immediately changes what every subsequent test is worth.
- **Two of the three worst bugs in this repository were invisible because nothing tested the orchestrator.** That is the whole argument for Group B. The bugs were not subtle; they were three-line control-flow errors in a file nobody had opened.
- **`3-analyze/analyze.py:7-17` is the documentation standard this repository should meet.** It explains the context-window truncation arithmetic, the reasoning, and the trade-off, in a comment, at the point where a future maintainer needs it. Several other modules have comments that contradict their code — the sentiment chunk size being the clearest example. When fixing those, make the comment true rather than deleting the reasoning.
- **The `issues/008` file is a good example of the documentation that does work.** It states the problem with a real log excerpt, gives a table of options with their trade-offs, and has explicit acceptance criteria and a "blocked by" section. If the review's four PRDs are the output of this pass, the natural follow-up is decomposing them into issue stubs in this format.
- **Run `make test` before and after the Makefile change** and confirm the test count changes. It is a one-line verification that the most important fix in this pass actually took effect.
- **The `logs/` directory footgun will surface the first time anyone tests on a fresh clone.** Every submission script writes its output to a path under it, the scheduler opens that file before the script body runs, and the script's own directory creation is therefore too late. It is a two-character fix per script and it belongs here in Group G — but expect it to be the first thing a new operator hits.
