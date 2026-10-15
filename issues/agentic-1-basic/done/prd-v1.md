# PRD: SLICK+ Knowledge Agent (10-agent)

## Problem Statement

Employees in operational environments — manufacturing, care, logistics, HR, compliance — generate valuable tacit knowledge through short instructional videos (Slicks). This knowledge is indexed and searchable in Qdrant, but it is only accessible via direct semantic search queries. There is no conversational interface, no way to synthesise across multiple videos, no way to generate structured artefacts (summaries, checklists, playlists) from that content, and no governance mechanism to ensure AI-generated output is reviewed before being trusted.

Employees cannot ask natural-language questions and receive grounded, cited answers. They cannot ask the system to build them an onboarding playlist, a safety checklist, or a step-by-step SOP — and even if they could, there is no record of who approved that output or when. The knowledge exists but is not yet actionable.

## Solution

A standalone terminal agent — `agent.py` — that runs on a developer's PC or directly on HPC via an interactive session. The agent uses LangGraph to orchestrate a Qwen2.5 language model (served via Ollama) with a set of tools that read from and write to the existing Qdrant knowledge base.

Users interact with the agent through a conversational CLI loop. The agent can answer questions with timestamped, source-grounded citations, retrieve full transcripts, and generate artefacts such as summaries and playlists. All read operations are instant. All write operations pause the agent and require explicit human approval before anything is persisted — the approver's identity and timestamp are recorded alongside the artefact.

The agent runs identically in Docker (`docker run`) and Singularity (`singularity exec`), connecting to Qdrant and Ollama as external services configured via environment variables. The HuggingFace model cache is bind-mounted rather than baked into the image.

## User Stories

1. As a developer, I want to run `docker run -it slickplus/agent:latest` and immediately start a conversational session with the video knowledge base, so that I can test and demo the agent without any local Python setup.
2. As a developer on HPC, I want to run `singularity exec agent.sif bash -c "python agent.py"` inside an `srun` interactive session, so that the agent has direct access to Qdrant and Ollama running on the same cluster.
3. As a developer, I want to configure Qdrant and Ollama hostnames via environment variables, so that the same container works whether I am tunnelling from a laptop or running natively on HPC.
4. As a developer, I want the HuggingFace model cache bind-mounted from the host, so that the container does not re-download the embedding model on every run.
5. As a user, I want to type a natural-language question at a `>` prompt and receive a synthesised answer drawn from the video knowledge base, so that I do not need to know which video or timestamp to look for.
6. As a user, I want every answer to include a numbered sources block showing the video title, creator, timestamp, and relevance score, so that I can verify the answer against the original content.
7. As a user, I want to ask questions in any of the five supported languages (English, Spanish, French, Mandarin, Arabic) and receive answers filtered to content in that language, so that multilingual teams are served equally.
8. As a user, I want to ask "show me everything uploaded by a specific creator" and receive a ranked list of their videos with relevant sections highlighted, so that I can find subject-matter expertise quickly.
9. As a user, I want to ask the agent to build me an onboarding playlist for a specific role or task, and receive an ordered list of videos with specific timestamp ranges and a reason for each inclusion, so that I can onboard new team members without manually curating content.
10. As a user, I want to ask the agent to summarise a specific video, and receive a structured summary before it is saved, so that I can review the AI output before it becomes part of the knowledge base.
11. As a user, I want to be shown a draft artefact (summary, checklist, playlist) and asked to approve or reject it with `y/n` before it is saved, so that I remain in control of what enters the knowledge base.
12. As a user, I want rejected artefacts to be discarded silently, so that the knowledge base is never polluted with unapproved content.
13. As a user, I want approved artefacts to be saved with my identity and a timestamp, so that there is an audit trail of who approved what and when.
14. As a user, I want the agent to keep working autonomously across multiple tool calls until it has a complete answer or artefact, so that I do not need to manually chain queries.
15. As a user, I want the agent to retrieve the full transcript of a video when I ask detailed questions about it, so that answers are not limited to short chunk windows.
16. As a user, I want the agent to explain its reasoning — which videos it searched, what it found — before presenting a final answer, so that I can follow the chain of thought.
17. As a developer, I want all agent tools to be pure Python functions in a single `tools.py` module, so that they can be tested in isolation and reused by a future MCP server without changes.
18. As a developer, I want the LangGraph agent state and graph definition to be separate from the CLI entry point, so that the agent logic can be tested headlessly without a running terminal.
19. As a developer, I want the system prompt and all prompt templates centralised in a single `prompts.py` file, so that prompt engineering changes do not require touching agent logic.
20. As a developer, I want an `agent` service added to the existing `docker-compose.yml` at the project root, so that the full stack (Qdrant, Ollama, embed-server, index-server, and agent) can be brought up with a single command without duplicating existing service definitions.
21. As a developer, I want an HPC launch script that wraps the `singularity exec` call with the correct bind mounts and environment variables, so that HPC users do not need to memorise the full command.
22. As a developer, I want the agent to exit cleanly with a non-zero code if Qdrant or Ollama are unreachable at startup, so that misconfigured environments fail fast with a clear error message.

## Implementation Decisions

### Modules

### Folder structure and build order

`10-agent/` follows the existing convention established in `2-inference/` and `6-embed/`:

```
10-agent/
    agent.py              # LangGraph agent + CLI loop
    tools.py              # tool functions (deep module)
    prompts.py            # prompt templates
    tests/                # pytest test suite
    local/                # Step 1 — run directly, no container
        run.sh            # starts agent.py with correct env vars
    docker/               # Step 2 — containerised
        Dockerfile
        requirements.txt
        build.sh          # builds slickplus/agent:latest
    hpc/                  # Step 3 — HPC Singularity
        run.sh            # singularity exec wrapper
        build-sif.sh      # converts Docker image to SIF
```

**Build order:** local → docker → HPC. Each stage must be working before the next is built. Local development uses `local/run.sh` pointing at a tunnelled or local Qdrant/Ollama. Docker packages the same code. HPC converts the Docker image to a SIF file.

### Modules

**`10-agent/tools.py` — Tool functions (deep module)**
The core of the system. Exposes six pure functions:
- `search_knowledge_base(query, lang, top_k)` — embeds the query with `multilingual-e5-large`, queries Qdrant `video_chunks`, returns a list of `{video_id, file, text, timestamp_start, timestamp_end, score}`.
- `get_video_metadata(video_id)` — fetches the full payload from Qdrant `video_metadata` for a given video.
- `get_full_transcript(video_id)` — scrolls all chunks for a video from `video_chunks`, returns them ordered by timestamp as a single concatenated transcript with timestamps.
- `generate_summary(video_id)` — calls `get_full_transcript` internally, sends to Qwen via Ollama, returns a draft summary string. Does not persist anything.
- `generate_playlist(goal)` — calls `search_knowledge_base` multiple times with varied sub-queries, reasons over results via Qwen, returns an ordered list of `{video_id, title, timestamp_start, timestamp_end, reason}`. Does not persist anything.
- `save_artefact(type, content, video_ids, approved_by)` — writes the artefact to Qdrant `video_artefacts` collection with `type`, `content`, `source_video_ids`, `approved_by`, and `approved_at` fields.

All functions are stateless and accept only primitive types or simple dicts. No LangGraph or agent state leaks into this module.

**`10-agent/prompts.py` — Prompt templates**
Contains the system prompt describing the agent's role, tool use instructions, citation format requirements, and language behaviour. Also contains any few-shot examples used in tool-calling prompts. No logic — pure strings and f-string templates.

**`10-agent/agent.py` — LangGraph agent + CLI**
Defines the LangGraph state graph: a `think` node (Qwen decides which tool to call), a `tool` node (executes the tool), an `interrupt` node (pauses for human approval on write operations), and a `respond` node (streams final answer to terminal). Entry point is the `main()` CLI loop: reads user input, runs the graph, prints the result, loops until `exit`.

**`10-agent/local/run.sh` — local launch script**
Sets `QDRANT_HOST`, `OLLAMA_HOST`, `HF_HOME` and calls `python agent.py` directly. No container. Follows the pattern of `6-embed/local/1-start-embed-server.sh`.

**`10-agent/docker/Dockerfile` — container image**
Base image: `python:3.11-slim`. Installs dependencies from `docker/requirements.txt` (`langgraph`, `langchain-ollama`, `qdrant-client`, `sentence-transformers`). Copies `10-agent/` contents. Sets `ENTRYPOINT ["python", "agent.py"]`. Does not include model weights — model cache is bind-mounted at runtime. Follows the pattern of `6-embed/docker/Dockerfile`.

**`10-agent/hpc/run.sh` — HPC Singularity launch script**
Singularity exec wrapper. Sets `PROJECT_ROOT` using `$PWD/../..` (srun interactive pattern from existing repo conventions). Binds project root as `/workspace` and `.hf_cache` as the HuggingFace cache dir. Passes `QDRANT_HOST` and `OLLAMA_HOST` from environment. Follows the pattern of `2-inference/hpc/infer-on-gpu.sh`.

**`10-agent/hpc/build-sif.sh` — SIF build script**
Converts the Docker image to a Singularity SIF file and copies it to `/scratch/project_465003359/mcgowank/agent.sif`. Follows the naming and storage convention of `whisper-hpc.sif`.

**`docker-compose.yml` (project root) — existing file, extended**
A `docker-compose.yml` already exists at the project root defining `qdrant`, `ollama`, `embed-server`, `index-server`, and `dev` services. The agent is added as a new `agent` service to this file — it is not a separate compose file. The `agent` service builds from `10-agent/docker/Dockerfile`, depends on `qdrant` and `ollama` (both already defined), uses Docker service hostnames (`qdrant:6333`, `ollama:11434`) for internal networking, and bind-mounts `.hf_cache`. No existing service definitions are modified.

### Interfaces

**Environment variables (all configurable)**
- `QDRANT_HOST` — default `localhost:6333`
- `OLLAMA_HOST` — default `localhost:11434`
- `LLM_MODEL` — default `qwen2.5:14b`
- `EMBED_MODEL` — default `intfloat/multilingual-e5-large`
- `HF_HOME` — default `/root/.cache/huggingface`

**Qdrant collections used (read)**
- `video_chunks` — 1024-dim cosine, payload: `video_id`, `file`, `lang`, `timestamp_start`, `timestamp_end`, `text`
- `video_metadata` — payload: `video_id`, `file`, `lang`, `title`, `tags`, `uploaded_by`, `sentiment_label`, `sentiment_score`

**Qdrant collections used (write)**
- `video_artefacts` — new collection, 1-dim placeholder vector, payload: `type` (`summary`|`playlist`|`checklist`), `content`, `source_video_ids`, `approved_by`, `approved_at`

**Agent response format (terminal output)**
```
Answer:
<synthesised answer text>

Sources:
  [1] <title>  •  <timestamp>  •  <uploaded_by>  •  score: <score>
  [2] ...
```

**Approval prompt (terminal, write operations only)**
```
<draft artefact displayed>

Save this <type> to the knowledge base? [y/n]
```

On `y`: calls `save_artefact`, prints confirmation with artefact ID, approver, timestamp.
On `n`: discards silently, returns to `>` prompt.

### Architecture decisions

- The embed model used for query embedding in `search_knowledge_base` is the same `intfloat/multilingual-e5-large` used by the existing `6-embed/embed_server.py` — no new model required.
- Qwen2.5 is used for all generation (summarisation, playlist reasoning, answer synthesis). Ollama serves it; the agent connects via `langchain-ollama`.
- LangGraph `interrupt()` is used for the approval gate. The graph checkpoints state before the interrupt so the approval prompt is resumable if the session is interrupted.
- The `save_artefact` tool is only callable from within the `interrupt` node — it cannot be called by the LLM directly. This is enforced at the graph level, not via prompt instructions.
- Video stitching (physical ffmpeg concatenation) is explicitly deferred to v2. The agent produces logical playlists only.
- MCP server is explicitly deferred to v2. `tools.py` is designed as a clean interface so that wrapping it in an MCP server later requires no changes to tool logic.

## Testing Decisions

**What makes a good test for this system:**
Tests should verify the external behaviour of each module — what goes in, what comes out — without asserting on internal implementation details such as which Qdrant query method was called or how many times Ollama was invoked. Tests should use dependency injection or environment variable overrides rather than monkeypatching internals.

**Modules to test:**

`tools.py` — highest priority. Each tool function should be tested with a mock Qdrant client and a mock Ollama response. Tests verify: correct Qdrant collection is queried, correct query vector prefix (`query:` vs `passage:`) is used, response is correctly shaped, `save_artefact` writes to the correct collection with all required fields including `approved_by` and `approved_at`.

`agent.py` graph — medium priority. Test that a read-only query path does not trigger the interrupt node. Test that a write-generating path does trigger the interrupt node and that the graph halts awaiting input. Use LangGraph's test utilities to drive the graph headlessly without a real terminal.

`prompts.py` — low priority. Smoke test that prompt templates render without errors given valid inputs.

**Prior art in this codebase:**
No existing test suite. New tests should be placed in `10-agent/tests/` and follow standard `pytest` conventions consistent with the Python version used in the Dockerfile.

## Out of Scope

- Public web UI — no HTTP server, no Chainlit, no React frontend in v1.
- Local desktop UI popup — a browser-based chat UI (e.g. Gradio) served from a `chat_server.py` FastAPI wrapper around the agent is a planned v2 path. The architecture supports this with minimal effort: `tools.py` is UI-agnostic, and adding a `/chat` endpoint + a new Docker Compose service is sufficient. System tray, Electron, and VS Code extension variants are also viable at that point.
- MCP server — tools.py is MCP-ready but the MCP transport layer is v2.
- Physical video stitching via ffmpeg — playlists are logical (ordered timestamp lists) only.
- Metadata schema changes — `review_status`, `permissions`, `playlist_ids` fields are not added to existing Qdrant collections in v1.
- Multi-user sessions — the agent is single-user, single-session; no auth or session management.
- Fine-grained permission checks — the agent does not enforce per-video permissions in v1.
- Streaming token output — the agent waits for a complete LLM response before printing; streaming is a v2 UX improvement.
- New language models beyond Qwen2.5 — model selection is fixed via environment variable.

## Further Notes

- The SIF file for the agent (`agent.sif`) should follow the same naming and storage convention as the existing `whisper-hpc.sif` at `/scratch/project_465003359/mcgowank/`.
- The agent's `hpc/run.sh` should follow the `srun` interactive pattern from `2-inference/hpc/` (using `$PWD` not `SLURM_SUBMIT_DIR`), not the `sbatch` pattern from `1-train/hpc/`.
- The `docker-compose.yml` at the project root already exists and defines the full pipeline stack. The agent is a new service added to it. It is the single entrypoint for local full-stack development.
- When running the full Docker stack, both `embed-server` and `agent` will load `multilingual-e5-large` into memory independently. This is acceptable for development. If memory becomes a constraint, the agent's `search_knowledge_base` tool can be refactored to call `embed-server` at `http://embed-server:8765/embed` instead of loading the model directly — this is a v2 optimisation.
- Qwen2.5:14B is the recommended model size. If GPU memory on HPC is constrained, Qwen2.5:7B is a viable fallback and should be documented in the README.
- The approval gate records the current OS username (`os.getlogin()`) as `approved_by` in v1. A proper identity system is a v2 concern.
