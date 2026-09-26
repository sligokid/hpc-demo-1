# 8-search — Semantic Search

CLI tool for querying the indexed video transcript chunks in Qdrant. Encodes the query with the same model used at index time (`intfloat/multilingual-e5-large`) and returns the top-k most semantically similar chunks with file path and timestamp.

**Depends on:** Qdrant (port 6333), indexed `video_chunks` collection

---

## Files

| File | Description |
|---|---|
| `search.py` | Encodes a query and runs a nearest-neighbour search against `video_chunks` |
| `test_search.py` | Unit tests (SentenceTransformer and QdrantClient mocked) |
| `local/1-search.sh` | Convenience wrapper — runs a query from the project root |

---

## How it works

1. The query string is prefixed with `query:` and encoded with `multilingual-e5-large` (`normalize_embeddings=True`). This asymmetric prefix is the counterpart to the `passage:` prefix applied to chunks at index time — omitting it degrades retrieval quality.
2. The resulting 1024-dim vector is sent to Qdrant's `query_points` against the `video_chunks` collection.
3. If `--lang` is supplied, a payload filter restricts results to chunks whose `lang` field matches exactly.
4. The top-k hits are returned as a JSON array, scored and sorted by cosine similarity (highest first).

---

## Usage

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

Or via the convenience wrapper (passes `$1` as the query, with a default):

```bash
8-search/local/1-search.sh "how can i find out more about the club"
```

---

## Output

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

## Limitations

**Model loads from disk on every call.** `multilingual-e5-large` is ~2 GB. Each invocation of `search.py` loads it fresh, waits for it to initialise, runs one query, then exits. For interactive use or latency-sensitive applications, wrap `search()` in a long-lived process or expose it as a service endpoint.

**Language filter is exact-match on the stored `lang` payload field.** The value must match exactly what was written at index time (e.g. `"en"`, `"es"`, `"zh"`). There is no fallback to cross-lingual search if no results exist for the requested language.

**No result deduplication.** If a video was indexed multiple times (e.g. after a pipeline re-run), duplicate chunks can appear in results. IDs are deterministic so re-indexing overwrites existing points, but if `video_id` changed between runs both versions will be present.

**`top_k` is a hard limit, not a score threshold.** Results below a meaningful similarity score are returned alongside high-confidence hits. Callers should apply their own score cutoff if low-relevance results are a problem.

---

## Tests

```bash
pytest 8-search/ -v
```

SentenceTransformer and QdrantClient are both mocked — no model weights or running Qdrant instance required.
