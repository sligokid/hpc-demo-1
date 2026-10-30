# PRD: 12-tts — Teleprompter-to-Audio TTS Stage

## Problem Statement

After an SOP is generated and converted into a speech-optimised teleprompter script, there is no way to automatically produce an audio version of that script. Users must manually copy the teleprompter content into a TTS tool, which breaks the automated pipeline and adds friction for content creators who need a narrated audio output alongside the written document.

## Solution

Add a standalone `12-tts` module that takes a `{stem}.teleprompter.md` file, extracts only the Audio fields from its structured table format, and converts them to a single concatenated WAV audio file (`{stem}.teleprompter.wav`) using the Ollama phonon TTS model via its HTTP API. The module follows the same three-target deployment pattern as all other pipeline modules: local shell script, Docker container, and SLURM HPC array job via Singularity.

## User Stories

1. As a content creator, I want a WAV audio file generated automatically from my teleprompter script, so that I do not have to manually feed the text into a TTS tool.
2. As a pipeline operator, I want TTS generation to be idempotent, so that re-running the stage does not regenerate files that already exist.
3. As a pipeline operator, I want the TTS stage to be standalone (not embedded in pipeline.py), so that I can run it independently on any teleprompter file regardless of how it was produced.
4. As a developer, I want the TTS module to extract only the Audio fields from the teleprompter markdown, so that visual cues and section headings are not spoken aloud in the output.
5. As a developer, I want `[PAUSE]` markers stripped before sending text to phonon, so that the spoken audio does not include literal marker text.
6. As a content creator, I want long scripts chunked at sentence boundaries and concatenated into a single WAV, so that the 4096-character API limit does not produce split or truncated audio files.
7. As an operator, I want the TTS voice to be configurable via environment variable and CLI argument, so that I can choose different voices per project without modifying code.
8. As a local developer, I want a simple shell script (`local/run.sh`) that runs TTS against any teleprompter file, so that I can test the stage without Docker or SLURM.
9. As a DevOps engineer, I want a Dockerfile and `run-tts.sh` script for the TTS module, so that I can run it in a containerised environment with a network-accessible Ollama service.
10. As a DevOps engineer, I want a `docker-buildx-publish.sh` script, so that I can build and push a linux/amd64 image to Docker Hub from an Apple Silicon machine.
11. As an HPC operator, I want a SLURM sbatch script that runs TTS via Singularity, so that I can process batches of teleprompter files on the cluster.
12. As an HPC operator, I want a submit script that scans for pending `.teleprompter.md` files and generates a timestamped manifest before submitting a SLURM array job, so that I can process all pending files in one command.
13. As an HPC operator, I want a polling script that resubmits the submit script every 10 minutes, so that new teleprompter files are processed automatically without manual intervention.
14. As an HPC operator, I want the polling loop stoppable via `scancel --name`, so that I can halt unattended processing cleanly.
15. As a developer, I want the TTS module to use the Ollama `POST /v1/audio/speech` HTTP API (not the CLI), so that it is consistent with how all other Ollama calls are made in the project.
16. As a developer, I want WAV concatenation done with Python's stdlib `wave` module, so that no additional audio dependencies are required.
17. As an operator, I want the HPC script to read the Ollama endpoint from the same endpoint file used by other HPC stages, so that no extra configuration is needed on the cluster.
18. As a developer, I want the module to gracefully skip files whose output WAV already exists, so that partial runs or re-runs do not duplicate work.
19. As a developer, I want the TTS module to have a clean CLI interface (`--input`, `--output`, `--ollama-host`, `--voice`), so that it can be called from any orchestration context.
20. As a content creator, I want the audio output to be a 16-bit mono 24kHz WAV file, matching the phonon API default, so that playback is compatible with standard media players without conversion.

## Implementation Decisions

### Modules

- **`12-tts/tts.py`** — Core module. Responsibilities: parse teleprompter markdown to extract Audio field content, strip `[PAUSE]` markers and residual markdown, split plain text into sentence-boundary chunks under 4096 characters, call `POST /v1/audio/speech` for each chunk, concatenate raw WAV responses into a single output file using the stdlib `wave` module. Exposes a `generate(input_path, output_stem, ollama_host, voice)` function and a CLI entry point.
- **`12-tts/requirements.txt`** — `requests` only. `wave` is stdlib. No additional audio dependencies.
- **`12-tts/local/run.sh`** — Bash wrapper: resolves project root, accepts `<teleprompter-file>` as positional arg, derives lang/stem, calls `tts.py` directly. Respects `OLLAMA_HOST` and `VOICE` env vars.
- **`12-tts/docker/Dockerfile`** — `python:3.11-slim` base, linux/amd64. Installs `requirements.txt`, copies `tts.py`. Entrypoint: `python /app/tts.py`.
- **`12-tts/docker/run-tts.sh`** — Runs the Docker image with `sync/input` mounted read-only and `sync/output` mounted read-write. Auto-builds the image if not present. Respects `OLLAMA_HOST`, `VOICE`, `TTS_IMAGE` env vars.
- **`12-tts/docker/docker-buildx-publish.sh`** — Builds and pushes `sligokid/tts-tools:latest` for linux/amd64 from project root context.
- **`12-tts/hpc/tts-sbatch.sh`** — SLURM array task. Reads manifest, derives SOP file path per array index, runs `tts.py` via `singularity exec` with `bash -c` wrapper for `LD_LIBRARY_PATH`. Binds project root as `/workspace` using `SLURM_SUBMIT_DIR`. Reads Ollama endpoint from file at `$SCRATCH/ollama.endpoint`.
- **`12-tts/hpc/tts-hpc-submit.sh`** — Scans `sync/input/*/` for `*.teleprompter.md` files whose `*.teleprompter.wav` does not yet exist in `sync/output/`. Writes timestamped manifest to `logs/`. Submits SLURM array job.
- **`12-tts/hpc/tts-hpc-poll.sh`** — SLURM job that calls `tts-hpc-submit.sh` and reschedules itself every 10 minutes via a trap on EXIT. Stoppable with `scancel --name=G-tts`.

### API Contract

- **Endpoint:** `POST http://{ollama_host}/v1/audio/speech`
- **Request body:** `{"model": "phonon", "input": "<plain text>", "voice": "<voice name>"}`
- **Response:** raw WAV bytes (streamed); read with `response.content`
- **Chunk limit:** 4096 characters per request
- **Output format:** 16-bit PCM, mono, 24kHz WAV (phonon default)

### Teleprompter Audio Extraction

The teleprompter markdown uses a two-column table structure. Audio content lives in rows of the form `| Audio | <spoken text> |`. Extraction regex: match lines where the first cell is `Audio` and capture the second cell. After extraction, strip `[PAUSE]` markers, then strip any residual markdown symbols before chunking.

### Chunking Strategy

Split extracted plain text into sentences (split on `.`, `!`, `?` followed by whitespace or end of string). Accumulate sentences into a chunk until adding the next sentence would exceed 4096 characters, then flush. Each chunk is sent as a separate API call. All response WAV buffers are concatenated in order using `wave.open` in write mode, copying frames from each chunk's in-memory WAV.

### HPC Conventions

- SIF file: `/scratch/project_465003359/mcgowank/tts-tools.sif`
- SLURM account: `project_465003359`
- SLURM partition: `small`
- Project root binding: `--bind "$PROJECT_ROOT:/workspace"` using `SLURM_SUBMIT_DIR` for sbatch scripts

### Idempotency

`tts.py` returns early without making any API calls if the output `.teleprompter.wav` already exists.

## Testing Decisions

Good tests for this module test external behaviour only: given a teleprompter markdown file with known Audio fields, the output WAV is produced with correct structure. Tests should mock the Ollama HTTP call (return a minimal valid WAV bytes object) and assert on file creation, idempotency, and correct extraction logic.

### Modules to test

- **`12-tts/tts.py`** — unit tests covering:
  - Audio field extraction from teleprompter markdown (various section structures)
  - `[PAUSE]` marker stripping
  - Sentence-boundary chunking at the 4096-char limit
  - WAV concatenation correctness (valid WAV header, correct frame count)
  - Idempotency (no API call made if output already exists)

### Prior art

- `11-sop/test_sop.py` and `11-sop/test_teleprompter.py` — both mock `_call_ollama` via `unittest.mock.patch` and assert on file output. The TTS tests should follow the same pattern, mocking `requests.post` to return a minimal WAV bytes payload.

## Out of Scope

- Integration into `pipeline.py` (TTS is standalone only)
- Multiple output formats (MP3, OGG, etc.) — WAV only
- Voice cloning or custom voice training
- Real-time streaming playback
- Multilingual TTS routing (phonon handles this internally)
- Subtitle/SRT generation from the audio
- Teleprompter generation itself (handled by `11-sop/teleprompter.py`)

## Further Notes

- The phonon model requires Ollama version 0.40.11 or later. Operators should verify their Ollama version before running this stage.
- `ollama pull phonon` must be run on the Ollama instance before the first TTS job.
- Available voices can be listed with `ollama show phonon` on the host running Ollama.
- On HPC, phonon runs on the same Ollama node as the LLM models — no additional GPU allocation is needed for the TTS sbatch job itself since the model runs server-side.
- The Docker image is CPU-only (no GPU needed client-side); the Ollama server handles all inference.
