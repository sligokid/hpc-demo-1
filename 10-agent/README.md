# 10-agent — Knowledge-Base Agent

LangGraph agent with a CLI chat loop for the indexed video knowledge base. `tools.py` wraps Qdrant queries behind three stateless functions; `prompts.py` centralises the system prompt and citation formatting; `agent.py` implements the LangGraph graph and CLI entry point.

**Depends on:** Qdrant (port 6333), Ollama (port 11434), indexed `video_chunks` and `video_metadata` collections.

---

## Models Used

| Model | Source | Role |
|-------|--------|------|
| `intfloat/multilingual-e5-large` | [HuggingFace](https://huggingface.co/intfloat/multilingual-e5-large) | Encodes search queries into 1024-dim vectors for nearest-neighbour lookup |
| `qwen2.5:3b` (via Ollama) | Ollama | LLM reasoning and tool-call decisions |

Must match the model used by `6-embed` at index time — using a different embed model will produce incompatible vectors and poor results. Query text is prefixed with `query:` before encoding (as required by E5). The `passage:` prefix is used at index time; `query:` is used here — omitting this asymmetry degrades retrieval quality.

---

## Quick start

```bash
# from the project root with venv active
bash 10-agent/local/run.sh
```

Type a question at the `>` prompt. Type `exit` to quit.

---

## Example questions

**Factual search** (`search_knowledge_base`):
```
What is Slick+ and how does it work?
What did Andrew Ng say about AI opportunities?
Tell me about the Sligo Triathlon Club
```

**Creator / title lookup** (`search_knowledge_base` → `get_video_metadata`):
```
Who created the video about bike fitting, and what is it about?
Which video features Linda Hegarty and what are the key topics?
Find videos about how to structure a Slick and tell me who made them
```

**Full transcript** (`get_full_transcript`):
```
Give me the full transcript of the Slick+ intro video
Show me the complete transcript of the InPost video
```

**Multi-hop** (agent calls multiple tools autonomously):
```
What are the main topics covered in the AI videos and who are the speakers?
```

---

## How it Works

The LangGraph graph has three nodes:

1. **`think`** — sends the conversation history and tool schema to Qwen (via Ollama `/api/chat`). If Qwen returns a tool call, the graph routes to `run_tool`. If it returns a plain answer, the graph routes to `respond`.
2. **`run_tool`** — dispatches to one of the three tool functions, appends the result as a tool message, and loops back to `think`.
3. **`respond`** — extracts the final answer and accumulated sources from state, then ends.

The graph cycles `think → run_tool → think` until Qwen has enough information to answer, then exits via `respond`.

### Tool functions

1. **`search_knowledge_base`** — prefixes the query with `query:`, encodes it with `multilingual-e5-large`, and runs a `query_points` call against the `video_chunks` collection. An optional `lang` argument restricts results to a single language code. Returns `{video_id, file, text, timestamp_start, timestamp_end, score}`.
2. **`get_video_metadata`** — scrolls the `video_metadata` collection for a given `video_id` and returns the full metadata payload (title, description, lang, creator, etc.).
3. **`get_full_transcript`** — paginates all chunks for a `video_id` from `video_chunks`, sorted by `timestamp_start`. Returns `{text, timestamp_start, timestamp_end}`.

All three accept `qdrant_client` and `embed_model` as injected keyword arguments — no module-level globals, keeping them mockable in tests.

---

## Files

| File | Description |
|---|---|
| `tools.py` | Three stateless read functions wrapping Qdrant |
| `prompts.py` | `SYSTEM_PROMPT`, `CITATION_TEMPLATE`, `LANG_INSTRUCTIONS`, `format_sources()` |
| `agent.py` | LangGraph graph (`think`/`run_tool`/`respond`), `_serialize_messages`, CLI `main()` |
| `local/run.sh` | Sources `local/.env`, exports env vars, runs `agent.py` |
| `local/.env.example` | All environment variables with defaults |
| `tests/test_tools.py` | 11 unit tests for the three tool functions (Qdrant mocked) |
| `tests/test_graph.py` | 8 graph path tests — full think→run_tool→respond cycle (Qdrant + Ollama mocked) |

---

## Running locally

**Prerequisites:** venv active, `pip install -r requirements.txt` done, Qdrant running with indexed data, Ollama running with `qwen2.5:3b` pulled.

```bash
# first time only — pull the model (~2 GB)
ollama pull qwen2.5:3b

cp 10-agent/local/.env.example 10-agent/local/.env
# edit QDRANT_HOST, OLLAMA_HOST etc. as needed
bash 10-agent/local/run.sh
```

---

## Tests

```bash
pytest 10-agent/tests/ -v
```

Qdrant client, embed model, and Ollama are fully mocked — no live services, model weights, or GPU required.

---

## Configuration

All settings are read from environment variables (populated by `local/run.sh` from `local/.env`):

| Variable | Default | Description |
|---|---|---|
| `QDRANT_HOST` | `localhost:6333` | Qdrant host:port |
| `OLLAMA_HOST` | `localhost:11434` | Ollama host:port |
| `LLM_MODEL` | `qwen2.5:3b` | Ollama model name |
| `EMBED_MODEL` | `intfloat/multilingual-e5-large` | HuggingFace embed model |
| `HF_HOME` | `~/.cache/huggingface` | HuggingFace model cache directory |

---

## Limitations

**Startup exits fast if services are unreachable.** The agent checks Qdrant and Ollama on startup and exits with a non-zero code and a clear error message if either is down.

**Model loads from disk on every cold start.** `multilingual-e5-large` is ~2 GB. For repeated use keep the process running rather than restarting.

**Language filter is exact-match.** The `lang` value must match exactly what was stored at index time (e.g. `"en"`, `"es"`). There is no fallback to cross-lingual search.

**`get_full_transcript` paginates in batches of 100.** For very long videos this issues multiple scroll requests. Results are always fully reassembled and sorted before returning.

**`top_k` is a hard limit, not a score threshold.** Low-relevance results are returned alongside high-confidence hits. Apply a score cutoff in the calling code if needed.
