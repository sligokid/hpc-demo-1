# 8-search — Semantic Search

CLI tool for querying the indexed video transcript chunks in Qdrant. Encodes the query with the same model used at index time (`intfloat/multilingual-e5-large`) and returns the top-k most semantically similar chunks with file path and timestamp.

**Depends on:** Qdrant (port 6333), indexed `video_chunks` collection

---

## Models Used

| Model | Source | Role |
|-------|--------|------|
| `intfloat/multilingual-e5-large` | [HuggingFace](https://huggingface.co/intfloat/multilingual-e5-large) | Encodes the search query into a 1024-dim vector for nearest-neighbour lookup |

Must match the model used by `6-embed` at index time — using a different model will produce incompatible vectors and poor results. Query text is prefixed with `query:` before encoding (as required by E5).

---

## How it Works

1. The query string is prefixed with `query:` and encoded with `multilingual-e5-large` (`normalize_embeddings=True`). This asymmetric prefix is the counterpart to the `passage:` prefix applied at index time — omitting it degrades retrieval quality.
2. The resulting 1024-dim vector is sent to Qdrant's `query_points` against the `video_chunks` collection.
3. If `--lang` is supplied, a payload filter restricts results to chunks whose `lang` field matches exactly.
4. The top-k hits are returned as a JSON array, scored and sorted by cosine similarity (highest first).

---

## Sample Output

JSON array printed to stdout, one object per result, ordered by descending score:

```json
[
  {
    "file": "inbox/en/safety-intro.mp3",
    "timestamp_start": 42.1,
    "score": 0.8923,
    "text": "Before touching any live components, isolate the circuit at the breaker and verify with a non-contact tester."
  },
  {
    "file": "inbox/en/electrical-basics.mp3",
    "timestamp_start": 118.5,
    "score": 0.8411,
    "text": "Lockout tagout procedures ensure no one re-energises the circuit while maintenance is underway."
  }
]
```

| Field | Description |
|---|---|
| `file` | Original audio file path as stored at index time |
| `timestamp_start` | Start of the chunk in seconds — use this to deep-link into the video |
| `score` | Cosine similarity in `[0, 1]`, rounded to 4 decimal places |
| `text` | Transcript text of the matching chunk |

---

## Files

| File | Description |
|---|---|
| `search.py` | Encodes a query and runs a nearest-neighbour search against `video_chunks` |
| `test_search.py` | Unit tests (SentenceTransformer and QdrantClient mocked) |
| `local/1-search.sh` | Convenience wrapper — runs a query from the project root |

---

## Running locally

```bash
# Basic query — top 5 results
python 8-search/search.py --query "how to isolate a circuit before working on it"

# Filter to Spanish content
python 8-search/search.py --query "cómo aislar un circuito" --lang es

# Retrieve more results
python 8-search/search.py --query "onboarding procedures" --top-k 10

# Point at a remote Qdrant instance
python 8-search/search.py --query "safety risk assessment" --qdrant-host 10.0.0.5:6333
```

Or via the convenience wrapper:

```bash
8-search/local/1-search.sh "how can i find out more about the club"
```

---

## Limitations

**Model loads from disk on every call.** `multilingual-e5-large` is ~2 GB. Each invocation loads it fresh, runs one query, then exits. For interactive or latency-sensitive use, wrap `search()` in a long-lived process or expose it as a service endpoint.

**Language filter is exact-match.** The `--lang` value must match exactly what was written at index time (e.g. `"en"`, `"es"`). There is no fallback to cross-lingual search if no results exist for the requested language.

**No result deduplication.** If a video was indexed multiple times with a different `video_id`, duplicate chunks can appear in results. IDs are deterministic so re-indexing with the same `video_id` overwrites existing points cleanly.

**`top_k` is a hard limit, not a score threshold.** Low-relevance results are returned alongside high-confidence hits. Apply your own score cutoff if needed.
