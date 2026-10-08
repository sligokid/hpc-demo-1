# PRD 02: Reclaim the Allocation — Correct SLURM Resource Requests

**Parent PRD:** `prd/task-2-company-brain/prd.md`
**Source:** Codebase review, 2026-09-29. All `file:line` citations were verified against the working tree on that date and will drift — re-verify before acting on any single line.
**Pass:** 2 of 4. Companions: [01 Stop the Bleeding](prd-01-stop-the-bleeding.md) · [03 Correctness](prd-03-correctness.md) · [04 Trustworthiness](prd-04-trustworthiness.md)

---

## Problem Statement

The project holds a LUMI-G allocation. A material fraction of it is spent on jobs that cannot use a GPU.

The clearest case: Qdrant, a pure CPU and RAM vector database, is scheduled with `--gres=gpu:1` on the `small-g` partition. It reserves a full MI250X GCD for eight hours to answer HTTP requests. The index server sitting in the same directory, which does the same kind of work, correctly requests `small` with no `--gres` at all — so the two scripts contradict each other inside one folder.

Second: `3-analyze/hpc/analyze-sbatch.sh` puts an array of pure HTTP clients on `small-g`. `analyze.py` makes a single `requests.post` to the Ollama daemon and writes a JSON file. Across an N-file array that is N node-slots on GPU nodes, for up to an hour each, consuming no GPU whatsoever.

Third: `2-inference/hpc/infer-on-cpu.sh` requests the GPU partition with no GPU, placing a CPU job on a GPU node for no benefit. The same mistake appears in `3-analyze/hpc/analyze-on-gpu.sh`, whose name promises a GPU it never gets.

Fourth, and most misleading: `1-train/hpc/train-sbatch-cpu.sh` is documented in `CLAUDE.md:47` as the "CPU-only fallback variant". It requests `--gres=gpu:1`, `--partition=small-g`, and `singularity exec --rocm` — identical resources to the GPU script — but with `--batch_size 64` against the same `--mem=64G`. A user reaching for the CPU fallback gets a second GPU job, and the more likely of the two to run out of memory. There is no CPU fallback in this repository.

Beyond the gross misallocations, two services are configured suboptimally in ways that cost allocation or walltime:

- The embed service sets no `HF_HOME`. Every eight-hour restart re-downloads `multilingual-e5-large` into the low-quota home directory. The training script in the same repository demonstrates the correct pattern and does it right.
- Ollama's GGUF weights are memory-mapped from Lustre, so every cold inference pays network page faults per token.

And a pipeline job will happily burn twenty minutes of GPU time transcribing a file, then discover at the analyze stage that the `llama3` model was never pulled. The service preflight checks that Ollama is *up*; nothing checks that the model is *present*.

---

## Solution

Correct the resource requests so that each job lands on the smallest partition that can run it, and fix the two service configurations that waste walltime or quota.

The substantive changes:

1. **Qdrant moves to `small` with no `--gres`.** It is a CPU/RAM workload and does not need a GCD.
2. **The analyze array moves to `small`.** It is an HTTP client.
3. **The CPU inference and analyze-on-GPU wrappers move to `small`.** Neither gets a GPU today; neither should sit on a GPU node.
4. **`train-sbatch-cpu.sh` is either fixed to genuinely run on CPU or deleted.** A script named "cpu" that requests a GPU is worse than no script, because it is a trap. If the CPU path is not wanted, deleting it and correcting `CLAUDE.md` is the honest fix.
5. **The embed service gets `HF_HOME`** pointed at project scratch, matching the pattern already used by the training job.
6. **Ollama models and Qdrant storage move to node-local scratch**, copied from project scratch at service start. Both are I/O-bound on network storage today for no reason.
7. **A model preflight runs before transcription**, not after.
8. **The remaining over-requests are trimmed** to realistic figures.

Partition selection throughout follows LUMI's own guidance: `small-g` is for workloads that genuinely need a GPU, `small` is LUMI-C and appropriate for everything else. Every script in the repo already sets `--account` correctly and requests a valid partition name — there are no typos and no illegal 64-core requests. This pass is about the resource *amounts*, not about the mechanics of requesting them.

---

## User Stories

1. As a LUMI project owner, I want jobs that cannot use a GPU to be scheduled on the CPU partition, so that my GPU allocation is available for work that needs it.
2. As a LUMI project owner, I want Qdrant to stop holding a GCD for eight hours, so that scarce GPU time goes to transcription and embedding.
3. As a LUMI project owner, I want the analyze array to run on CPU nodes, so that an N-file analysis does not occupy N GPU node slots.
4. As a LUMI project owner, I want resource requests to match actual work, so that my allocation is not consumed by idle reservations.
5. As a developer, I want the CPU inference script to actually run on CPU, so that the name describes the behaviour.
6. As a developer, I want `train-sbatch-cpu.sh` to either be a real CPU path or not exist, so that I cannot accidentally submit a second GPU job believing I chose the fallback.
7. As a developer, I want the documentation to stop pointing at a "CPU-only fallback variant" that requests a GPU, so that I make the right choice from the docs alone.
8. As a developer, I want the embed model cached on project scratch, so that service restarts do not re-download the model into the low-quota home directory.
9. As an operator, I want the embed service to start fast after a restart, so that the twelve-hour restart cycle does not lose time to a model download.
10. As an operator, I want Ollama's weights on local disk, so that cold inference is not paying Lustre page faults per token.
11. As an operator, I want Qdrant's vector store on local disk, so that indexing and search are not network round-trips.
12. As an operator, I want the pipeline to check that the `llama3` model is present *before* transcribing, so that a missing model costs seconds instead of twenty minutes of GPU time.
13. As an operator, I want a failed preflight to name the missing model and the command to fix it, so that I do not have to infer the cause from a log.
14. As a developer, I want the training job's walltime to reflect how long it actually takes, so that it returns to the queue instead of sitting idle for hours.
15. As a developer, I want memory requests sized to the workload, so that jobs are not queued behind unnecessary memory reservations.
16. As a developer, I want the two MIOpen cache strategies in the training scripts to agree, so that five concurrent array tasks are not all writing to shared Lustre storage.
17. As a reviewer, I want scripts that hold a GPU to have a comment justifying why, so that future over-requests are visibly deliberate.
18. As an operator, I want a second Qdrant instance to be prevented from silently overwriting the endpoint file, so that the first instance is not orphaned holding a GCD.
19. As an operator, I want a local-disk fallback when node scratch is unavailable, so that the service still starts rather than failing outright.
20. As a maintainer, I want the resource request for each job recorded in one table, so that drift between scripts is visible in review.
21. As a developer, I want the local and Docker paths to use the same model identifiers, so that a model that works in one environment is not missing in another.
22. As an operator, I want the model pull to be idempotent and cheap when the model is already present, so that restarts do not re-download it.
23. As a developer, I want `--rocm` passed only to jobs that actually touch the GPU runtime, so that CPU jobs do not depend on ROCm libraries being present in their SIF.
24. As an operator, I want the correct SIF set documented, so that a fresh deployment starts every service the pipeline requires.

---

## Implementation Decisions

### Modules

**`7-index/hpc/1-qdrant-serve-sbatch.sh` — remove the GPU request**
- Drop `--gres=gpu:1` (line 17) and switch `--partition=small-g` to `small` (line 24).
- Bring the request in line with its sibling `2-index-serve-sbatch.sh:27`, which already does this correctly.
- Add a comment stating that Qdrant is CPU/RAM only, so the next reviewer does not re-add the GPU.

**`3-analyze/hpc/analyze-sbatch.sh` — move to the CPU partition**
- `--partition=small-g` (line 24) becomes `small`. The job body (lines 77-84) makes one HTTP call and writes a file.
- No `--gres` line is added or removed — there is none, which is correct.

**`2-inference/hpc/infer-on-cpu.sh` — move to the CPU partition**
- `--partition=small-g` (line 12) becomes `small`.
- Note that this script also omits the `bash -c "..."` wrapper that the project documents as mandatory so that `LD_LIBRARY_PATH` applies inside the container. For a genuinely CPU-only run this is defensible, but it should be a comment explaining the deliberate deviation rather than an inconsistency.

**`3-analyze/hpc/analyze-on-gpu.sh` — honest naming**
- The `srun` block (lines 34-41) requests `small-g` with no `--gres`, so it gets no GPU. The work is a remote HTTP call.
- Either rename the script to reflect that it queries a remote service, or accept the partition change and document the naming mismatch. Renaming is preferable — a script named `on-gpu` that never gets a GPU will mislead the next reader regardless of its partition.

**`1-train/hpc/train-sbatch-cpu.sh` — fix or delete**
- As written it requests `--gres=gpu:1` (line 24), `--partition=small-g` (line 31), and `--rocm` (line 61), with `--batch_size 64` (line 74) against the same `--mem=64G` as the GPU script.
- **Recommended: delete it and correct `CLAUDE.md:47`.** A real CPU training path for ROCm-era Whisper fine-tuning is a substantial piece of work with its own performance characteristics, and pretending otherwise with a 4× batch size on identical memory is the worst option. If the CPU path is genuinely wanted, it is its own project with its own walltime estimate.
- Whichever is chosen, `CLAUDE.md` and `README.md` must be updated in the same change. (The broader `CLAUDE.md` rewrite is scheduled in PRD 04; this specific claim is corrected here so the two PRDs do not conflict.)

**`6-embed/hpc/1-embed-serve-sbatch.sh` — model cache**
- Add an `HF_HOME` environment variable and a `--bind` of a project-scratch cache directory, following the pattern already established in `1-train/hpc/train-sbatch-gpu.sh:63-64`. That script is the reference implementation and should not need changes.
- The cache path follows the existing `SCRATCH=${SCRATCH:-...}` overridable convention.
- This script already resolves `PROJECT_ROOT` robustly by probing for the config file (lines 41-45) — the best pattern in the repository. Leave it alone.

**`3-analyze/hpc/2-ollama-serve-sbatch.sh` — local model storage**
- The models directory is currently bound from project scratch (line 67), and Ollama memory-maps the GGUF weights from there. Every cold inference takes network page faults.
- At service start, copy the model directory to the node's local scratch and bind that instead. Fall back to the shared path if local scratch is unavailable or the copy fails, so the service still starts.
- The declared `WALL_TIME` variable at line 33 is never referenced by anything — either use it to compute the `--begin` offset for the resubmit, or delete it. A dead variable that claims to mirror `#SBATCH --time` will drift silently.

**`7-index/hpc/1-qdrant-serve-sbatch.sh` — local vector storage**
- The same treatment for the Qdrant storage directory: prefer node-local scratch, fall back to shared.
- The `QDRANT__SERVICE__MAX_REQUEST_SIZE_MB=256` setting (line 71) is duplicated by hand in `docker-compose.yml:37`. Extract it to a single source so the HPC and Docker paths cannot diverge. (Also relevant to PRD 03, which touches the request-size ceiling.)

**Model preflight — new, before transcription**
- `pipeline-hpc-sbatch.sh:33-49` verifies the Ollama *service* is up. It does not verify the `llama3` *model* is present. A job therefore transcribes a full file, then fails at the analyze stage.
- Add a preflight that queries the Ollama tags endpoint for the configured model name and exits immediately with a clear message if it is absent.
- The preflight happens before transcription, so a missing model costs seconds rather than twenty minutes of GPU.
- `3-analyze/hpc/3-ollama-pull-llama3.sh` already validates a SIF exists (lines 29-33) and an endpoint file exists (lines 37-41) and verifies the pull against `ollama list` (lines 59-73). That script is the reference for what a good preflight looks like in this repo.

**Qdrant singleton enforcement**
- The port preflight (lines 60-63) only catches a collision on the *same node*. A second Qdrant job lands on a different node, finds the port free, succeeds, and overwrites the shared endpoint file — orphaning the first instance, which holds a GCD for eight hours with nothing pointing at it.
- After the `--gres` removal this costs CPU rather than GPU, but the orphan is still a correctness problem. Use a Slurm lock on the endpoint file, or check whether a live Qdrant is already answering before starting.

**Trimmed over-requests**

| Script | Current | Proposed | Rationale |
|---|---|---|---|
| `1-train/hpc/train-sbatch-gpu.sh:28` | `--time=08:00:00` | ~01:00:00 | FLEURS is roughly 2–3k utterances per language; 3 epochs at batch 16 on `whisper-small` is on the order of a few hundred steps. Measure one real run before committing to a number. |
| `2-inference/hpc/infer-on-gpu.sh:16` | `--mem=128GB` | ~16G | Single-file `whisper-small` inference. Note the `GB` suffix here versus `G` elsewhere; standardise while touching it. |
| `1-train/hpc/train-sbatch-cpu.sh:74` | `--batch_size 64` | — | Removed with the script (see above). |

**Training MIOpen consistency**
- The two training scripts use opposite strategies: the GPU variant sets `MIOPEN_DISABLE_CACHE=1`, the CPU variant binds a MIOpen cache directory into project scratch (lines 68-69), which up to five concurrent array tasks would write to simultaneously.
- Once the CPU script is resolved, only one strategy remains. If a cache is genuinely wanted, it belongs on node-local scratch, not shared Lustre.

**Model identifier consistency**
- The same model is spelled three ways: `llama3`, `llama3:latest`, and a commented-out `llama3.1:8b`. Ollama resolves bare names to `:latest`, so this is cosmetic, but the preflight added above must match the pull script's spelling exactly or it will report a present model as missing.
- `issues/008-larger-context-model.md` proposes moving to `llama3.1:8b` for its 128k context window. **This PRD's preflight must be model-name-agnostic** so that adopting `llama3.1:8b` does not require reworking it. Read the model name from `pipeline.yaml`.

### Architectural decisions

- **`small-g` is for work that needs a GPU.** Every job that lands there without a `--gres` line, or with one it cannot use, is a mistake. LUMI's own documentation frames `small-g` as being for applications that can only use a single GPU.
- **A GPU request must be justified in a comment.** After this pass, any script carrying `--gres` states in a comment why the GPU is required. This makes future over-requests visibly deliberate rather than accidental.
- **Node-local scratch for anything read on a hot path.** Model weights and vector storage are both read constantly. Neither belongs on network storage. Shared scratch is for inputs, outputs, and caches that must outlive the job.
- **Fail before spending, not after.** The preflight principle generalises: check the expensive dependency before the expensive work, not after.
- **Documented names must match behaviour.** A script named `cpu` that requests a GPU is a trap, and so is a doc that calls it a fallback.

### Deliverables

| # | Deliverable | Description |
|---|---|---|
| 1 | Qdrant resource fix | Drop `--gres`, `small-g` → `small`, add justifying comment |
| 2 | Analyze array partition fix | `small-g` → `small` |
| 3 | CPU inference partition fix | `small-g` → `small`; document the `bash -c` deviation |
| 4 | `analyze-on-gpu.sh` resolved | Rename to reflect that it is a remote query, and fix its partition |
| 5 | `train-sbatch-cpu.sh` resolved | Deleted (recommended) or genuinely made CPU-only; docs corrected in the same change |
| 6 | Embed model cache | `HF_HOME` + scratch bind, following the training script's pattern |
| 7 | Ollama local model storage | Copy to node scratch at start, with fallback |
| 8 | Qdrant local storage | Same treatment for the vector directory |
| 9 | Model preflight | Verify the configured model is present before transcription; name comes from config |
| 10 | Qdrant singleton enforcement | Prevent a second instance orphaning the first |
| 11 | Request-size constant | Single source for the Qdrant max request size across HPC and Docker |
| 12 | Trimmed over-requests | Training walltime, inference memory, measured before committing |
| 13 | Resource request table | One table recording every job's partition and resource rationale |
| 14 | Dead variable cleanup | Unused `WALL_TIME`; MIOpen strategy unified |

---

## Testing Decisions

Resource requests are configuration, and configuration is testable by assertion rather than by execution. The valuable test is a guard, not a performance measurement.

**Bats assertions on resource directives.** For every sbatch script, assert that `--partition=small-g` appears only where a `--gres=gpu` line is also present and justified. This is a single cheap test that would have caught findings 1, 2, and 3 simultaneously, and it prevents the regression class permanently. Add it to `tests/shell.bats` alongside the existing Ollama service tests.

**Bats assertion on `--rocm`.** Assert that `singularity exec --rocm` appears only in scripts that also request a GPU. This catches the `analyze-on-gpu.sh` inconsistency and the `train-sbatch-cpu.sh` trap in the same sweep.

**Pre-flight test for the model check.** With a mocked Ollama tags endpoint, assert the job exits non-zero with a message naming the model when the model is absent, and proceeds when it is present. Use a counter-driven mock binary as `tests/shell.bats` already does for the Ollama pull test (lines 77-92) — that is the direct prior art in this repo.

**Cache-path test.** Assert the embed service script binds a scratch cache path and sets `HF_HOME`, so a future edit cannot silently drop it back to the default home directory.

**Local-storage fallback test.** Assert the Ollama and Qdrant services start successfully when node-local scratch is unavailable, falling back to the shared path. A service that only works on a well-provisioned node is worse than one that is slower everywhere.

**What is not tested here:** actual GPU utilisation, actual inference throughput, and real partition behaviour. These require submitting to LUMI. Measure one real training run to calibrate the walltime reduction in deliverable 12 before committing to a specific number — the proposal in this document is a starting estimate, not a measured figure.

---

## Out of Scope

- **A real CPU training path.** If `train-sbatch-cpu.sh` is wanted as an actual fallback rather than deleted, that is a separate project with its own performance characterisation.
- **Reducing the number of stages or changing which models are used.** The model swap proposed in `issues/008-larger-context-model.md` is a separate decision; this PRD only requires the preflight to be agnostic about which model is configured.
- **Node-partition optimisation for co-scheduling.** Placing services on the same node to minimise network hops is a larger scheduling exercise.
- **The Qdrant request-size ceiling as a performance issue.** The 256 MB limit is extracted as a constant here, but the underlying full-vector JSON round-trip is a PRD 03 concern.
- **The `/health` endpoint lying about model state.** A real correctness bug in the embed service — scheduled for PRD 03.
- **Pipeline failure semantics.** The case where a job discovers a missing dependency only after expensive work is addressed by the preflight; the general problem of jobs failing late and silently is PRD 01.
- **Removing the Werkzeug development server from the services.** A genuine production-hardening gap, but it is a correctness and security item, not an allocation one.

---

## Further Notes

- **LUMI `--mem` is per node, not per task.** Requesting `--mem=64G` on a 512 GiB node with four GCDs permits roughly eight co-resident jobs, each nominally holding 64 GiB. This is normal on LUMI and often intended. It does mean the `--mem` values in this repository are weaker signals than they look, and that trimming them (deliverable 12) helps queue position less than removing a `--gres` does. The `--gres` removals are the high-value changes; the memory trims are hygiene.
- **LUMI-G nodes expose eight GCDs to Slurm** (four MI250X, two GCDs each), so `--gres=gpu:1` is one GCD with 64 GB of HBM, not a whole GPU. Holding one for a CPU workload is still holding a quarter of a node's accelerators.
- **The automatic requeue interacts with resource changes.** A node failure re-runs a job body. For the self-resubmitting chains this re-arms the `EXIT` trap and produces duplicate poll chains. Add `--no-requeue` and `--open-mode=append` while editing these directives — the requeue problem itself is PRD 01.
- **`3-analyze/hpc/2-ollama-serve-sbatch.sh` and the embed service are the two genuine GPU consumers in this system.** Everything else — Qdrant, the index server, the analyze clients, the sync loop, the graph builder — is CPU work. After this pass, the GPU footprint is limited to Ollama, the embedding server, and the training and inference jobs, which is the correct shape.
- **SIF dependency check.** `9-graph/hpc/graph-sbatch.sh:98,121` sets `LD_LIBRARY_PATH` to a ROCm path inside a CPU-partition container built from the API SIF, which may not contain `/opt/rocm` at all. Harmless today, but it is exactly the copy-paste habit that produced findings 1 and 2. Remove it while in the neighbourhood.
- **Verify the model pull is idempotent before relying on the preflight.** `3-analyze/hpc/3-ollama-pull-llama3.sh` runs `ollama pull` against a compute-node service from a login node, which is a long network-heavy operation on a shared machine. The preflight is cheap; the pull is not. Making the pull skip an already-present model reduces the blast radius of the preflight firing.
