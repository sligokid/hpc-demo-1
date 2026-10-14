# 10-agent — Knowledge-Base Agent

LangGraph agent with a conversational CLI for the indexed video knowledge base. Supports factual Q&A with cited sources, full transcript retrieval, AI-generated summaries, and playlist generation — all with a human approval gate before anything is written to Qdrant.

**Depends on:** Qdrant (port 6333), Ollama (port 11434), indexed `video_chunks` and `video_metadata` collections.

---

## Models (used by this agent)

| Model | Source | Role |
|---|---|---|
| `intfloat/multilingual-e5-large` | HuggingFace | Encodes queries to 1024-dim vectors. Must match the model used by `6-embed` at index time. |
| `qwen2.5:3b` (via Ollama) | Ollama | LLM reasoning, tool-call decisions, summarisation, playlist curation |

Query text is prefixed with `query:` before encoding (E5 asymmetric retrieval). The `passage:` prefix is used at index time — omitting this asymmetry degrades retrieval quality.


## Quick start

```bash
# first time only — pull the model (~2 GB)
ollama pull qwen2.5:3b

cp 10-agent/local/.env.example 10-agent/local/.env
# edit QDRANT_HOST, OLLAMA_HOST etc. as needed
bash 10-agent/local/run.sh
```

Type a question at the `>` prompt. The agent remembers the full conversation for the session. Type `exit` to quit.

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

**Summary Generation** (`generate_summary`):
```
Create a summary of the Slick+ intro video
Create a summary of the InPost video
Create a summary of the bike fitting video
```

**Playlist Generation ** (`generate_playlist`):
```
Create a Into to Slick Playlist
Create a playlist of videos for a beginner triathlete



**Multi-hop** (agent calls multiple tools autonomously):
```
What are the main topics covered in the AI videos and who are the speakers?
```

---

## How it Works

### Graph topology

```
                 ┌─────────────────┐
   start ──────▶ │     think       │
                 └────────┬────────┘
              tool call?  │  plain answer?
            ┌─────────────┴──────────────┐
            ▼                            ▼
     ┌─────────────┐              ┌─────────────┐
     │  run_tool   │              │   respond   │──▶ END
     └──────┬──────┘              └─────────────┘
 artefact?  │  no artefact?
┌───────────┴──────────┐
▼                      └──▶ think (loop)
┌──────────────┐
│ ask_approval │
│  interrupt() │
└──────┬───────┘
  y/n  └──▶ END
```

**`think`** — sends the full conversation history and tool schema to Qwen (Ollama `/api/chat`). Routes to `run_tool` if Qwen calls a tool, or to `respond` if it returns a plain answer.

**`run_tool`** — executes the chosen tool and appends the result to the message history. Routes back to `think` (read tools) or to `ask_approval` (if `generate_summary` or `generate_playlist` produced a draft artefact).

**`respond`** — formats the final answer and sources block, then ends.

**`ask_approval`** — uses LangGraph `interrupt()` to pause the graph, display the draft artefact, and prompt `[y/n]`. On `y`: calls `save_artefact` with the OS username and a timestamp. On `n`: discards silently. `save_artefact` is not in the tool schema — the LLM cannot call it directly.

### Conversation memory

A single `thread_id` is generated at session start and passed to every `graph.invoke()` call. The `MemorySaver` checkpointer replays the full message history into Qwen on each turn, so follow-up questions and clarifications work naturally within a session. History does not persist between sessions (process restart = blank slate).

### Tool functions

| Tool | Collection | Description |
|---|---|---|
| `search_knowledge_base` | `video_chunks` | Embeds query with E5, returns top-k `{video_id, text, timestamp, score}` |
| `get_video_metadata` | `video_metadata` | Returns full metadata payload for a `video_id` |
| `get_full_transcript` | `video_chunks` | Scrolls all chunks for a video, sorted by timestamp |
| `generate_summary` | — | Gets full transcript, summarises via Qwen. Draft only — does not save. |
| `generate_playlist` | — | Multi-query search + Qwen ordering. Draft only — does not save. |
| `save_artefact` | `video_artefacts` | Persists approved artefact with `approved_by` + `approved_at`. Not callable by LLM. |

---

## Files

| File | Description |
|---|---|
| `tools.py` | Six tool functions (3 read, 2 generate, 1 write) |
| `prompts.py` | `SYSTEM_PROMPT`, `SUMMARISE_PROMPT`, `PLAYLIST_PROMPT`, `CITATION_TEMPLATE`, `format_sources()` |
| `agent.py` | LangGraph graph, all nodes and routing, `_serialize_messages`, CLI `main()` |
| `local/run.sh` | Sources `local/.env`, exports env vars, runs `agent.py` |
| `local/.env.example` | All environment variables with defaults |
| `tests/test_tools.py` | 11 unit tests — read tool functions (Qdrant mocked) |
| `tests/test_graph.py` | 8 graph path tests — read path (Qdrant + Ollama mocked) |
| `tests/test_artefacts.py` | 12 tests — generate/save tools and approval gate graph paths |

---

## Configuration

| Variable | Default | Description |
|---|---|---|
| `QDRANT_HOST` | `localhost:6333` | Qdrant host:port |
| `OLLAMA_HOST` | `localhost:11434` | Ollama host:port |
| `LLM_MODEL` | `qwen2.5:3b` | Ollama model name |
| `EMBED_MODEL` | `intfloat/multilingual-e5-large` | HuggingFace embed model |
| `HF_HOME` | `~/.cache/huggingface` | HuggingFace model cache directory |

---

## Tests

```bash
pytest 10-agent/tests/ -v
```

31 tests. Qdrant, embed model, and Ollama are fully mocked — no live services or GPU required.

---

## Limitations

**Conversation history is in-memory only.** History survives for the duration of the process. Restarting the agent starts a fresh session. See `issues/todo/019-agent-persistent-conversation-history.md` for the persistent history path.

**Startup exits fast if services are unreachable.** Checks Qdrant and Ollama on startup; exits with a non-zero code and a clear error if either is down.

**Model loads from disk on every cold start.** `multilingual-e5-large` is ~2 GB. Keep the process running for repeated use.

**Language filter is exact-match.** The `lang` value must match exactly what was stored at index time (`"en"`, `"es"`, etc.). No cross-lingual fallback.

**`top_k` is a hard limit, not a score threshold.** Low-relevance results are returned alongside high-confidence hits.
