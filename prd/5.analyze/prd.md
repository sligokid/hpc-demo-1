# PRD: Ollama on HPC — Persistent GPU Inference Service for Metadata Generation

## Problem Statement

After transcribing training videos with Whisper on HPC, users want to run `analyze.py` to generate structured metadata using a local LLM. The existing `analyze.py` assumes Ollama is running on `localhost:11434`, which is not viable on an HPC cluster: compute nodes have no internet access, Docker is unavailable, and a fresh Ollama process started per-job wastes GPU warm-up time and risks model weight re-loading on every task. There is no established pattern for running Ollama as a shared, persistent GPU service within SLURM, nor for pre-pulling model weights into scratch storage for air-gapped operation.

## Solution

A persistent Ollama inference service runs as a dedicated SLURM job on a GPU node, containerised in a separate Singularity image with ROCm passthrough. It writes its `hostname:port` to a known file in scratch on startup. A one-time model pull script downloads model weights into scratch before any jobs run, enabling fully offline operation thereafter. A SLURM array job reads the endpoint discovery file and runs `analyze.py` across a directory of transcripts in parallel. `analyze.py` gains an `--ollama-host` flag so it can reach the remote service. A convenience `srun` wrapper covers the interactive single-transcript use case. Together these components extend the existing pipeline so that transcription and metadata generation can be submitted as a single end-to-end HPC workflow.

## Pipeline Position

```
audio files
    │
    ▼
infer array job  ──►  transcripts/
                           │
                           ▼
                    analyze-batch.sh  ──►  metadata JSONs
                           │
                           ▼ (reads endpoint)
                    ollama.endpoint (scratch)
                           ▲
                    ollama-serve.sh (persistent GPU job)
```

## User Stories

1. As a developer, I want to run a single SLURM batch script to start a persistent Ollama service on a GPU node, so that I do not have to start and stop Ollama for every transcript.
2. As a developer, I want the Ollama service to run inside a Singularity container with ROCm passthrough, so that it uses the cluster's AMD GPUs without requiring root or Docker.
3. As a developer, I want a separate `ollama.sif` image for the Ollama service, so that it is independently versioned and does not bloat the existing `whisper-hpc.sif` image.
4. As a developer, I want the Ollama service job to write its `hostname:port` to a known file in scratch on startup, so that downstream analysis jobs can discover the endpoint automatically without hardcoding a node name.
5. As a developer, I want the endpoint discovery file to be written atomically, so that analysis jobs that start concurrently do not read a partial or empty file.
6. As a developer, I want a one-time model pull script that downloads Ollama model weights into scratch storage, so that compute nodes can load models without internet access.
7. As a developer, I want the model pull script to verify that the model was downloaded successfully before exiting, so that I know the offline cache is complete before submitting analysis jobs.
8. As a developer, I want model weights stored in a shared scratch path co-located with the existing HuggingFace cache, so that all jobs on the project allocation share one copy and do not re-download per user.
9. As a developer, I want `analyze.py` to accept an `--ollama-host` flag, so that it can reach a remote Ollama service instead of assuming `localhost:11434`.
10. As a developer, I want `--ollama-host` to default to `localhost:11434`, so that existing local usage of `analyze.py` is not broken.
11. As a developer, I want a SLURM array batch script (`analyze-batch.sh`) that reads a directory of transcript files and submits one task per file, so that many transcripts can be processed in parallel.
12. As a developer, I want `analyze-batch.sh` to read the Ollama endpoint from the scratch discovery file, so that I do not need to pass the hostname manually when submitting analysis jobs.
13. As a developer, I want `analyze-batch.sh` to fail with a clear error if the endpoint discovery file does not exist, so that I know the Ollama service job has not started yet.
14. As a developer, I want each analysis task to write its JSON output to a file named after the transcript (e.g. `metadata/foo.json` for `transcripts/foo.txt`), so that outputs are traceable back to their source.
15. As a developer, I want `analyze-batch.sh` to log per-task stdout and stderr to `logs/`, following the existing `%A_%a.out` naming convention, so that failures are easy to diagnose.
16. As a developer, I want a convenience `srun` wrapper script for interactive single-transcript analysis, so that I can test the pipeline end-to-end without writing a batch script.
17. As a developer, I want the `srun` wrapper to accept the transcript file path as its only positional argument, so that the interface is simple and consistent with existing `infer-on-gpu.sh`.
18. As a developer, I want the `srun` wrapper to read the endpoint discovery file automatically, so that I do not need to know which node the Ollama service is running on.
19. As a developer, I want the Ollama service job to request enough GPU memory to load the default model (llama3 8B, ~5 GB weights), so that the job does not fail at model load time.
20. As a developer, I want the Ollama service job to stay alive for a configurable wall-clock time (default 8 hours), so that it outlasts a typical batch analysis run without tying up resources indefinitely.
21. As a developer, I want the Ollama service job to clean up the endpoint discovery file on exit via a trap, so that stale endpoint files do not mislead future jobs.
22. As a developer, I want the Ollama service to perform a health-check loop after starting, writing the endpoint file only once the HTTP API responds, so that downstream jobs do not attempt to connect before the server is ready.
23. As a developer, I want the analysis batch job to support `--dependency=after` on the Ollama service job, so that tasks do not start before the service is ready when submitting both in one command.
24. As a developer, I want the `--model` flag in `analyze.py` to remain functional, so that I can use mistral or any other model available in the Ollama scratch cache without code changes.
25. As a developer, I want a README section documenting the end-to-end HPC workflow (pull model → start service → submit analysis), so that team members can reproduce the pipeline without tribal knowledge.
26. As a developer, I want the Ollama service to bind to a fixed port (default 11434) on the compute node, so that the discovery file format is predictable and simple.
27. As a developer, I want a clear error message if the port is already in use on the allocated node, so that I can re-submit or choose a different port.
28. As a developer, I want all new SLURM scripts to use the same `--account` and `--partition` values as existing scripts, so that jobs are charged to the correct project allocation.
29. As a developer, I want the Singularity bind mounts for the Ollama service to expose the scratch model cache directory as `OLLAMA_MODELS` inside the container, so that the Ollama process finds pre-pulled weights without environment-specific path changes.
30. As a content producer, I want to submit a single command that chains transcription, Ollama service start, and batch metadata generation, so that the full pipeline runs unattended overnight.

## Implementation Decisions

### Modules

- **`ollama-serve.sh`** — SLURM batch script. Allocates one GPU node. Starts Ollama inside `ollama.sif` with `--rocm` and scratch model cache bound as `OLLAMA_MODELS`. Runs a health-check loop until `GET /api/tags` returns 200, then writes `$HOSTNAME:11434` to the endpoint discovery file atomically. Stays alive for the configured wall time. Cleans up the discovery file on exit via a `trap` on `EXIT`/`TERM`.

- **`ollama-pull.sh`** — Standalone setup script (not a SLURM job; run once on a login node or data-transfer node with internet access). Executes `ollama pull <model>` inside `ollama.sif` with the scratch model cache bound, then verifies the model is listed in `ollama list`. Accepts model name as a positional argument, defaults to `llama3`.

- **`analyze-batch.sh`** — SLURM array job. Reads the transcript directory to build a list of `.txt` files, maps `SLURM_ARRAY_TASK_ID` to a file, reads the Ollama endpoint from the discovery file, and calls `analyze.py --transcript <file> --ollama-host <endpoint>`. Writes output JSON to `metadata/<basename>.json`. Fails fast if the discovery file is absent.

- **`analyze-on-gpu.sh`** — Interactive `srun` wrapper. Reads the discovery file, launches a single `srun` task that calls `analyze.py` for the transcript passed as `$1`. Analogous to the existing `infer-on-gpu.sh`.

- **`analyze.py`** (modified) — Add `--ollama-host` CLI flag (default `localhost:11434`). Construct the Ollama API URL from this flag rather than a hardcoded constant. No other behaviour changes.

### Key architectural decisions

- **Persistent service, not per-job sidecar** — Starting Ollama inside every analysis task wastes 30–60 seconds of GPU time per job on model loading. A single persistent service amortises startup cost across all tasks and keeps the GPU occupied efficiently.

- **File-based endpoint discovery** — The service writes `hostname:port` to a well-known scratch path. This requires no external coordination service and works in air-gapped environments. The file is created only after the health check passes, providing an implicit readiness signal.

- **Separate `ollama.sif`** — Keeps the Ollama container independently versioned. The existing `whisper-hpc.sif` is ROCm/PyTorch-heavy; Ollama has its own ROCm runtime bundled. Mixing them risks library version conflicts and produces a very large image.

- **ROCm passthrough via `--rocm` flag** — Mirrors the existing pattern in `submit-gpu.sh` and `infer-on-gpu.sh`. CPU inference is available as a fallback if the `--rocm` flag is omitted, but GPU is the primary target.

- **Scratch-resident model weights** — Ollama model weights (GGUF files) are stored in the project scratch space alongside the existing HuggingFace cache. This enables air-gapped operation after the one-time pull and avoids re-downloading across users or sessions.

- **`--dependency=after` for coordinated submission** — When submitting both service and analysis jobs together, `sbatch --dependency=after:<service_jobid> analyze-batch.sh` ensures analysis tasks start only after the service job has been allocated. The health-check loop and file-based discovery handle the finer-grained readiness within that window.

- **`trap EXIT` for cleanup** — The endpoint discovery file is removed when `ollama-serve.sh` exits for any reason (wall-time expiry, scancel, node failure). This prevents stale endpoints from being used by future jobs.

### API contract change in `analyze.py`

The Ollama base URL moves from a hardcoded string to a value derived from `--ollama-host`. The HTTP call becomes `http://<ollama_host>/api/generate`. Default behaviour (`localhost:11434`) is unchanged for local use.

### Directory conventions

```
/scratch/<project>/<user>/
    hf_cache/          # existing HuggingFace cache
    ollama-models/     # new: Ollama GGUF weight cache (OLLAMA_MODELS)
    ollama.endpoint    # new: written by ollama-serve.sh at startup, deleted on exit

$PWD/
    transcripts/       # input: one .txt file per video
    metadata/          # output: one .json file per transcript
    logs/              # SLURM stdout/stderr (existing convention)
```

## Testing Decisions

**What makes a good test:** test externally observable behaviour. Given known inputs (a transcript file, a mock Ollama endpoint), assert the correct outputs (a well-formed JSON file, a correct API URL, a non-zero exit code on failure). Do not test SLURM scheduler internals or Ollama model weights.

**Modules to test:**

- **`analyze.py` — `--ollama-host` flag:** assert that the constructed HTTP request URL uses the value of `--ollama-host` rather than `localhost:11434`. Mock `requests.post` at the HTTP boundary, consistent with the approach specified in the metadata PRD.

- **`analyze.py` — remote host error handling:** mock a `ConnectionError` to a non-localhost host and assert exit code 1 with a message that includes the configured host address, so users know which endpoint failed.

- **`ollama-serve.sh` — health-check loop:** mock the `curl` call to `/api/tags` to return non-200 twice then 200; assert the endpoint file is written only after the successful response.

- **`ollama-serve.sh` — cleanup trap:** assert the endpoint file is removed when the script receives `SIGTERM`.

- **`analyze-batch.sh` — missing discovery file:** invoke the script without a discovery file present and assert it exits non-zero with a descriptive error.

- **`ollama-pull.sh` — successful pull:** mock `ollama list` to return the expected model name and assert the script exits 0.

- **`ollama-pull.sh` — failed pull:** mock `ollama list` to return an empty list and assert the script exits non-zero.

**Approach:** Python tests mock at the HTTP boundary (`requests.post`). Shell script behaviour is tested with `bats` (Bash Automated Testing System), consistent with the project's shell-heavy toolchain.

## Out of Scope

- Multi-node Ollama deployments or model sharding across GPUs.
- NVIDIA/CUDA support — this PRD targets AMD ROCm exclusively, matching the cluster hardware.
- Automatic scaling of the Ollama service (e.g. starting additional service jobs when the queue is long).
- A REST API or web UI wrapping the Ollama service.
- Model fine-tuning or LoRA adaptation via Ollama.
- Streaming responses from Ollama — `analyze.py` uses the blocking `/api/generate` endpoint.
- Metrics collection or GPU utilisation dashboards for the Ollama service job.
- Support for models larger than available GPU VRAM without quantisation — model selection remains the user's responsibility.
- Automatic failover if the Ollama service job is cancelled mid-run.
- Running Ollama on a login node — login nodes are shared and typically prohibit GPU use.

## Further Notes

- The Ollama ROCm image (`ollama/ollama:rocm`) is the recommended base for `ollama.sif`. It bundles its own ROCm runtime, so host ROCm version mismatch risk is lower than with PyTorch-based images, but it should be validated against the cluster's driver version before production use.
- The health-check loop in `ollama-serve.sh` should have a timeout (e.g. 120 seconds) and exit non-zero if Ollama never becomes ready, to prevent the job from silently hanging.
- For very long analysis runs, request a wall time 30 minutes longer than the analysis array's expected duration to account for scheduling delays between job submission and job start.
- The `OLLAMA_MODELS` environment variable is the standard way to redirect Ollama's model storage; it is respected by both the Ollama binary and the `ollama pull` command, making it the correct hook for scratch-resident weights.
- If the cluster scheduler places multiple array tasks on the same node as the Ollama service, loopback (`localhost`) will work — but file-based discovery via `$HOSTNAME` remains correct and portable across all placement scenarios.
- Future extension: if batch sizes grow beyond what a single 8B model can handle in the allocated wall time, the `--model` flag in `analyze.py` makes it straightforward to switch to a quantised variant (e.g. `llama3:8b-q4`) for higher throughput at some quality cost.
