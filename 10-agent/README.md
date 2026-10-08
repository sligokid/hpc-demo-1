# 10-agent — Knowledge-Base Agent

Pure, testable tool functions that give an LLM agent read access to the indexed video knowledge base. `tools.py` wraps Qdrant queries behind three stateless functions; `prompts.py` centralises the system prompt and citation formatting. `agent.py` is a stub — the conversational loop is implemented in subsequent issues.

**Depends on:** Qdrant (port 6333), indexed `video_chunks` and `video_metadata` collections

---

## Models Used

| Model | Source | Role |
|-------|--------|------|
| `intfloat/multilingual-e5-large` | [HuggingFace](https://huggingface.co/intfloat/multilingual-e5-large) | Encodes search queries into 1024-dim vectors for nearest-neighbour lookup |

Must match the model used by `6-embed` at index time — using a different model will produce incompatible vectors and poor results. Query text is prefixed with `query:` before encoding (as required by E5). The `passage:` prefix is used at index time; `query:` is used here — omitting this asymmetry degrades retrieval quality.

---

## How it Works

1. **`search_knowledge_base`** — prefixes the query with `query:`, encodes it with `multilingual-e5-large`, and runs a `query_points` call against the `video_chunks` collection. An optional `lang` argument adds a payload filter so results are restricted to a single language code. Returns a list of `{video_id, file, text, timestamp_start, timestamp_end, score}` dicts.
2. **`get_video_metadata`** — scrolls the `video_metadata` collection with a `video_id` payload filter and returns the full metadata dict for that video. Returns an empty dict when the video is not found.
3. **`get_full_transcript`** — paginates through all chunks for a `video_id` in `video_chunks` and returns them sorted by `timestamp_start` as a list of `{text, timestamp_start, timestamp_end}` dicts.

All three functions accept `qdrant_client` and `embed_model` as injected keyword arguments — there are no module-level globals, which keeps them mockable and MCP-ready.

---

## Tools

### `search_knowledge_base(query, lang, top_k, *, qdrant_client, embed_model)`

```python
results = search_knowledge_base(
    "how to isolate a circuit before working on it",
    lang="en",
    top_k=3,
    qdrant_client=qdrant,
    embed_model=model,
)
```

```json
[
  {
    "video_id": "en/safety-intro",
    "file": "inbox/en/safety-intro.mp3",
    "text": "Before touching any live components, isolate the circuit at the breaker and verify with a non-contact tester.",
    "timestamp_start": 42.1,
    "timestamp_end": 48.6,
    "score": 0.8923
  }
]
```

### `get_video_metadata(video_id, *, qdrant_client)`

Returns the full payload dict written by `7-index` at index time — title, description, tags, lang, file path, and any other fields stored on the point.

### `get_full_transcript(video_id, *, qdrant_client)`

```json
[
  {"text": "Welcome to the safety induction.", "timestamp_start": 0.0,  "timestamp_end": 3.2},
  {"text": "Today we'll cover isolation procedures.", "timestamp_start": 3.2, "timestamp_end": 7.8}
]
```

Chunks are always returned ordered by `timestamp_start`, regardless of the order they were stored in Qdrant.

---

## Files

| File | Description |
|---|---|
| `tools.py` | Three stateless read functions wrapping Qdrant — `search_knowledge_base`, `get_video_metadata`, `get_full_transcript` |
| `prompts.py` | `SYSTEM_PROMPT`, `CITATION_TEMPLATE`, `LANG_INSTRUCTIONS`, and `format_sources()` helper |
| `agent.py` | Stub — conversational loop to be implemented in subsequent issues |
| `tests/test_tools.py` | 11 unit tests covering all three tool functions (Qdrant mocked) |
| `local/.env.example` | All environment variables with documented defaults |

---

## Running locally

**Prerequisites:** venv active, `pip install -r requirements.txt` done, Qdrant running with indexed data.

Copy and edit the env file:

```bash
cp 10-agent/local/.env.example 10-agent/local/.env
# edit QDRANT_HOST, OLLAMA_HOST, etc. as needed
```

Import the tools in a Python REPL or script:

```python
import os
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
from tools import search_knowledge_base, get_video_metadata, get_full_transcript

qdrant = QdrantClient(host="localhost", port=6333)
model  = SentenceTransformer("intfloat/multilingual-e5-large")

results = search_knowledge_base(
    "onboarding procedures",
    lang="en",
    top_k=5,
    qdrant_client=qdrant,
    embed_model=model,
)
```

---

## Tests

```bash
pytest 10-agent/tests/ -v
```

Qdrant client and embed model are fully mocked — no live services, model weights, or GPU required.

---

## Limitations

**Model loads from disk on every instantiation.** `multilingual-e5-large` is ~2 GB. For interactive or latency-sensitive use, instantiate `SentenceTransformer` once and pass it into each call.

**Language filter is exact-match.** The `lang` value must match exactly what was stored at index time (e.g. `"en"`, `"es"`). There is no fallback to cross-lingual search if no results exist for the requested language.

**`get_full_transcript` paginates in batches of 100.** For very long videos with many chunks this will issue multiple scroll requests. Results are always fully reassembled and sorted before returning.

**`top_k` is a hard limit, not a score threshold.** Low-relevance results are returned alongside high-confidence hits. Apply a score cutoff in the calling code if needed.
