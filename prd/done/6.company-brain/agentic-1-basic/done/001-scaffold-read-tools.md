## Parent PRD

`issues/prd-v1.md`

## What to build

Create the `10-agent/` directory structure and implement the three read-only tool functions in `tools.py`. This is the foundation every subsequent issue builds on.

The directory layout must follow the existing repo convention (`local/`, `docker/`, `hpc/` subfolders as in `2-inference/` and `6-embed/`). The Python files live at the root of `10-agent/`.

`tools.py` exposes three pure, stateless functions that read from Qdrant:
- `search_knowledge_base(query, lang, top_k)` — embeds the query using `intfloat/multilingual-e5-large` with the `query:` prefix, queries the `video_chunks` collection, returns a list of `{video_id, file, text, timestamp_start, timestamp_end, score}`.
- `get_video_metadata(video_id)` — fetches the full payload from `video_metadata` for a given video ID.
- `get_full_transcript(video_id)` — scrolls all chunks for a video from `video_chunks`, returns them ordered by `timestamp_start` as a list of `{text, timestamp_start, timestamp_end}`.

`prompts.py` contains the system prompt, citation format template, and language behaviour instructions. No logic — pure strings.

All Qdrant and Ollama connection details are read from environment variables (`QDRANT_HOST`, `OLLAMA_HOST`, `LLM_MODEL`, `EMBED_MODEL`, `HF_HOME`) with sensible defaults.

Tests in `10-agent/tests/` cover all three read functions using a mock Qdrant client. Tests verify response shape and that the correct collection is queried. Tests do not assert on internal implementation details.

## Acceptance criteria

- [ ] `10-agent/` directory exists with `agent.py` (stub), `tools.py`, `prompts.py`, `tests/`, `local/`, `docker/`, `hpc/` subfolders
- [ ] `search_knowledge_base` returns correctly shaped results from `video_chunks`
- [ ] `search_knowledge_base` uses the `query:` prefix when encoding (not `passage:`)
- [ ] `get_video_metadata` returns the full payload dict for a given `video_id`
- [ ] `get_full_transcript` returns chunks ordered by `timestamp_start`
- [ ] All three functions accept Qdrant client and embed model as injectable dependencies (not hardcoded globals)
- [ ] `prompts.py` exists with at minimum a `SYSTEM_PROMPT` string and a `format_sources()` helper
- [ ] `pytest 10-agent/tests/` passes with no live Qdrant required (mocked)
- [ ] All env vars have documented defaults in a `10-agent/local/.env.example` file

## Blocked by

None — can start immediately.

## User stories addressed

- User story 3 (env var configuration)
- User story 4 (HF cache bind-mount documented)
- User story 5 (search foundation)
- User story 6 (source citation data available)
- User story 7 (lang filter in search)
- User story 8 (metadata lookup)
- User story 15 (full transcript retrieval)
- User story 17 (tools.py as pure, testable, MCP-ready module)
- User story 19 (prompts.py centralised)
