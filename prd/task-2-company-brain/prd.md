# Task 2: The Company Brain

## Overview

SLICK+ has demonstrated end-to-end speech-to-knowledge extraction: fine-tuned Whisper transcribes multilingual audio, Llama 3 extracts structured metadata, and files sync bi-directionally with Google Drive via HPC. Task 2 extends this foundation into a searchable, personalised, sentiment-aware knowledge graph — the Company Brain.

The core proposition: every video uploaded to SLICK+ becomes a transcript, summary, checklist, skill signal, and searchable knowledge asset. Users find exact answers with timestamps. Managers see knowledge gaps, sentiment patterns, and emerging expertise. The right knowledge reaches the right person at the right time.

**Example:** A new hire joins a factory floor production line. On their first shift they search "how do I clear a jam on line 3" — instead of hunting through a paper manual or waiting for a supervisor, they get a ranked list of internal videos with the exact timestamp where an experienced line worker demonstrates the procedure in their own words, in the new hire's language. Their playlist is pre-populated with safety and operational content matched to the production operative role, ordered by relevance and filtered to exclude anything already watched. The knowledge graph shows that the line-jam video is closely related to three others on equipment maintenance and quality control checks — surfacing a practical onboarding path that no one explicitly curated. A floor manager reviewing the graph sees that equipment safety content skews negative in sentiment across the Arabic-language library, flagging a potential knowledge gap or team stress signal worth investigating.

---

## Problem Statement

The existing pipeline produces transcripts and JSON metadata but provides no way to search, relate, or personalise that knowledge. Content sits in flat files on Google Drive — a passive repository that employees must browse rather than query. There is no signal connecting videos to each other, no way to detect sentiment in organisational speech, and no personalised path through the content library.

---

## Goals

1. Make all video knowledge semantically searchable with timestamped retrieval across 5 languages
2. Surface relationships between videos as an interactive knowledge graph
3. Detect and store sentiment signals per video to identify tone, confidence, and organisational health
4. Generate personalised playlists per user based on role and watch history
5. Produce reproducible benchmark results for latency and multilingual retrieval accuracy

---

## Non-Goals (Phase 2)

- Fine-tuning `xlm-roberta` on silver labels (labelling pipeline ships in this PRD; training deferred)
- FastAPI or web frontend
- RAG Chat UI ("Ask Slick+")
- Richer behavioural signals (replay rate, Jira/Slack integrations, moment-of-need)
- Playlist delivery via API or HTML

---

## Development Phases

Every component MUST be built and verified in three environments in order. No component advances to the next environment until it passes verification in the current one.

### Phase 1 — Local (native Python)

Build and verify everything runs on a developer laptop using native Python, local Ollama, and Qdrant running as a local process.

**Environment:**
- Qdrant: `docker run -p 6333:6333 qdrant/qdrant` (or native binary)
- Ollama: `ollama serve` (native)
- Whisper: CPU inference via `venv`
- e5-large: CPU inference (slow but functional for smoke tests)

**Verification checklist:**
- [ ] `infer.py --segments` emits `segments.json` from a sample audio file
- [ ] `sentiment.py` scores a transcript and outputs `sentiment_label` + `sentiment_score`
- [ ] `embed-server.py` starts, accepts a chunk batch, writes to local Qdrant
- [ ] `pipeline.py` runs end-to-end on a single file through all 5 stages
- [ ] `search.py` returns timestamped results for a test query
- [ ] `graph.py` exports `graph.json` and `graph.html` opens in a browser
- [ ] `playlist.py` returns a ranked playlist for a test user profile
- [ ] `label.py` generates JSONL labels via local Ollama
- [ ] `benchmark.py` runs and produces a report

**Local startup sequence:**
```bash
# Terminal 1 — Qdrant
docker run -p 6333:6333 qdrant/qdrant

# Terminal 2 — Ollama
ollama serve

# Terminal 3 — Embedding worker
python 5-embed/embed-server.py --qdrant-host localhost:6333

# Terminal 4 — Run pipeline on a sample file
python pipeline.py --file sync/input/en/sample.mp3 --ollama-host localhost:11434
```

---

### Phase 2 — Docker (Docker Compose)

Package every new component into the existing Docker Compose setup. Each service gets a named container. The full pipeline must run with a single `docker compose up`.

**New Docker Compose services:**
```yaml
qdrant:
  image: qdrant/qdrant
  ports: ["6333:6333"]
  volumes: ["qdrant_storage:/qdrant/storage"]

embed-server:
  build: ./5-embed
  depends_on: [qdrant]
  environment:
    QDRANT_HOST: qdrant:6333
```

**Directory layout (mirrors existing pattern):**
```
5-embed/
  local/          # step-by-step local scripts
  docker/         # Docker Compose scripts and Dockerfile
  hpc/            # SLURM sbatch scripts
  embed-server.py
  sentiment.py
  label.py
  README.md
```

**Verification checklist:**
- [ ] `docker compose up` starts Qdrant + Ollama + embed-server with no manual steps
- [ ] `docker compose run --rm dev python pipeline.py --file ...` processes a file end-to-end
- [ ] `docker compose run --rm dev python search.py --query "..."` returns results
- [ ] `docker compose run --rm dev python graph.py` produces `graph.json`
- [ ] `docker compose run --rm dev python playlist.py --user ...` returns a playlist
- [ ] `docker compose run --rm dev python benchmark.py` produces a report
- [ ] All unit tests pass: `pytest 5-embed/test_*.py`

---

### Phase 3 — HPC (LUMI / SLURM + Singularity)

Deploy to LUMI using the established Singularity SIF + SLURM service job pattern. Qdrant and embed-server run as persistent SLURM daemon jobs alongside the existing Ollama service.

**New SIF images:**
```bash
# Build and push amd64 embed-server image
docker buildx build --platform linux/amd64 -t sligokid/whisper-embed:latest --push 5-embed/

# Pull SIFs on LUMI
singularity pull /scratch/project_465003209/mcgowank/whisper-embed.sif docker://sligokid/whisper-embed:latest
singularity pull /scratch/project_465003209/mcgowank/qdrant.sif docker://qdrant/qdrant:latest
```

**Verification checklist:**
- [ ] `qdrant-serve-sbatch.sh` starts Qdrant on a SLURM node, dashboard accessible
- [ ] `embed-serve-sbatch.sh` starts embed-server, connects to Qdrant
- [ ] Full pipeline processes a real audio file through all 5 stages on GPU nodes
- [ ] `search.py` returns results from the HPC-indexed Qdrant collection
- [ ] `graph.py` exports graph, `graph.html` renders correctly from Google Drive
- [ ] `playlist.py` returns a playlist from the HPC index
- [ ] `benchmark.py` runs on HPC and produces a report matching local/Docker baselines
- [ ] All outputs rclone correctly to Google Drive

---

## Architecture

### New Services

| Service | Local | Docker | HPC (SLURM) |
|---|---|---|---|
| Qdrant vector DB | `docker run qdrant/qdrant` | `docker compose up qdrant` | `5-embed/hpc/qdrant-serve-sbatch.sh` |
| Embedding worker | `python 5-embed/embed-server.py` | `docker compose up embed-server` | `5-embed/hpc/embed-serve-sbatch.sh` |

### Pipeline Stages (updated)

```
Google Drive                          LUMI HPC
────────────                          ──────────────────────────────────────────
whisper-sync/input/  ──rclone──►      sync/input/
                                           │
                                           ▼ pipeline-hpc-poll.sh
                                      ┌─────────────────────────┐
                                      │ Stage 2: TRANSCRIBE      │
                                      │ infer.py --segments      │
                                      │ → transcript.txt         │
                                      │ → segments.json          │  ← NEW
                                      └────────────┬────────────┘
                                                   │
                                                   ▼
                                      ┌─────────────────────────┐
                                      │ Stage 3: EXTRACT         │
                                      │ analyze.py               │
                                      │ → analysis.json          │
                                      │   + uploaded_by          │  ← NEW
                                      │   + date_processed       │  ← NEW
                                      └────────────┬────────────┘
                                                   │
                                                   ▼
                                      ┌─────────────────────────┐
                                      │ Stage 4: SENTIMENT       │  ← NEW
                                      │ sentiment.py             │
                                      │ xlm-roberta multilingual │
                                      │ → per-video aggregate    │
                                      │   score + label          │
                                      └────────────┬────────────┘
                                                   │
                                                   ▼ HTTP POST
                                      ┌─────────────────────────┐
                                      │ Stage 5: EMBED + INDEX   │  ← NEW SERVICE
                                      │ embed-server.py          │
                                      │ e5-large (GPU)           │
                                      │ → Qdrant                 │
                                      └────────────┬────────────┘
                                                   │
                                      ┌────────────▼────────────┐
                                      │ Qdrant service           │  ← NEW SERVICE
                                      │ collection: video_chunks │
                                      │ collection: video_meta   │
                                      │ dashboard: :6333         │
                                      └─────────────────────────┘
```

---

## Qdrant Schema

### Collection: `video_chunks`

One point per 3–5 Whisper segment group (~30–60 seconds of speech).

```json
{
  "vector": "<1024-dim float — e5-large>",
  "payload": {
    "file": "video.mp3",
    "lang": "es",
    "uploaded_by": "user@org.com",
    "date_processed": "2026-09-09T14:32:00Z",
    "timestamp_start": 42.5,
    "timestamp_end": 74.1,
    "text": "chunk text",
    "chunk_index": 3
  }
}
```

### Collection: `video_metadata`

One point per video, embedded from the `analyze.py` JSON output.

```json
{
  "vector": "<1024-dim float — e5-large>",
  "payload": {
    "file": "video.mp3",
    "lang": "es",
    "uploaded_by": "user@org.com",
    "date_processed": "2026-09-09T14:32:00Z",
    "title": "...",
    "description": "...",
    "tags": ["onboarding", "safety"],
    "goals": ["..."],
    "skills": ["..."],
    "sentiment_label": "positive",
    "sentiment_score": 0.83
  }
}
```

---

## Chunking Strategy

Whisper segments (natively timestamped) are grouped into windows of 3–5 segments (~30–60 seconds) with the timestamp anchored to the first segment in the group. This requires `infer.py` to emit `segments.json` alongside `transcript.txt`.

`segments.json` format:
```json
[
  {"start": 0.0, "end": 5.2, "text": "..."},
  {"start": 5.2, "end": 11.8, "text": "..."}
]
```

---

## Embedding Model

**`intfloat/multilingual-e5-large`**
- 1024-dim vectors
- Covers all 5 SLICK+ languages: en, es, fr, zh-CN, ar
- Requires GPU for production throughput
- Loaded once in `embed-server.py`; pipeline tasks POST chunks via HTTP

---

## Sentiment Analysis

**Model:** `cardiffnlp/twitter-xlm-roberta-base-sentiment` (multilingual, no GPU required for inference)

**Approach:**
- Run per transcript chunk during Stage 4
- Aggregate to per-video score (mean of chunk scores) + dominant label (positive / neutral / negative)
- Store `sentiment_label` and `sentiment_score` in `video_metadata` Qdrant payload
- Sentiment drives graph node colour and playlist ranking

**Fine-tuning data pipeline (ships in this PRD, training deferred to Phase 2):**
- `label.py` calls Llama 3 (already running in Stage 3) to label each transcript chunk as positive / neutral / negative with domain context in the prompt
- Outputs `labels/` directory of JSONL training data — ready for Phase 2 fine-tuning job

---

## Personalisation Engine

**User profile format (`profiles/<user>.json`):**
```json
{
  "user": "user@org.com",
  "role": "engineer",
  "language": "en",
  "watched": ["video-1.mp3", "video-3.mp3"]
}
```

**Playlist generation logic (`playlist.py`):**
1. Load user profile
2. Query `video_metadata` Qdrant collection filtered by `lang` matching user's language
3. Boost results whose `tags` overlap with role-relevant tags (role → tag mapping in `roles.yaml`)
4. Exclude already-watched videos
5. Rank remaining by cosine similarity to embeddings of watched videos (watch history as implicit preference signal)
6. Apply sentiment filter (configurable: prefer positive for onboarding, allow negative for risk training)
7. Return top-N ranked playlist as JSON

---

## Knowledge Graph

**`graph.py`** reads the `video_metadata` Qdrant collection and exports:

- `graph.json` — nodes (videos) and edges (shared tags), node attributes include `sentiment_label`, `lang`, `uploaded_by`, `tags`
- `graph.html` — self-contained D3.js/vis.js viewer that loads `graph.json` statically, no server required

Edge weight = number of shared tags between two videos. Nodes coloured by sentiment label. Filterable by language and uploaded_by in the browser.

---

## CLI Tools

| Script | Usage | Output |
|---|---|---|
| `search.py` | `python search.py --query "onboarding safety" --lang es --top-k 5` | JSON: file, timestamp_start, score, text |
| `graph.py` | `python graph.py --output sync/output/graph.json` | `graph.json` + `graph.html` |
| `playlist.py` | `python playlist.py --user user@org.com --top-n 10` | JSON: ranked video list with scores |
| `label.py` | `python label.py --transcripts sync/output/` | `labels/<stem>.jsonl` sentiment training data |
| `benchmark.py` | `python benchmark.py` | Benchmark report (see below) |

---

## Benchmarking

### B — Synthetic query recall

1. For each video, call Llama 3 to generate 3 natural-language questions answerable from its transcript
2. Run each question through `search.py`
3. Measure Recall@1, Recall@5, MRR across the full video library

### C — Cross-language retrieval

1. Take 10 videos that exist in 2+ languages (same content, different language)
2. Query in English, verify the non-English equivalent appears in top-5 results
3. Report cross-language retrieval rate

**Benchmark report format:** `benchmark-report.json` + `benchmark-report.md` summary, rcloned to Google Drive alongside transcripts.

---

## Deliverables

### Shared (all environments)

| # | File / Directory | Description |
|---|---|---|
| 1 | `2-inference/infer.py` | Add `--segments` flag, emit `segments.json` with Whisper timestamps |
| 2 | `5-embed/embed-server.py` | HTTP service, loads e5-large, accepts chunk batches, POSTs to Qdrant |
| 3 | `5-embed/sentiment.py` | Per-video sentiment scoring with xlm-roberta |
| 4 | `5-embed/label.py` | Llama 3 auto-labelling of transcript chunks for fine-tuning data |
| 5 | `pipeline.py` | Stage 4 (sentiment) + Stage 5 (embed + index) integration |
| 6 | `search.py` | CLI semantic search with lang / date / user filters |
| 7 | `graph.py` | Exports `graph.json` and `graph.html` |
| 8 | `graph.html` | Self-contained D3.js/vis.js knowledge graph viewer |
| 9 | `playlist.py` | CLI personalised playlist generator |
| 10 | `roles.yaml` | Role → tag mapping for playlist ranking |
| 11 | `profiles/` | Per-user profile JSON files |
| 12 | `benchmark.py` | Synthetic query + cross-language retrieval benchmark |
| 13 | `5-embed/test_embed.py` | Unit tests for embed-server, sentiment, label |

### Local

| # | File / Directory | Description |
|---|---|---|
| 14 | `5-embed/local/1-start-qdrant.sh` | Start Qdrant via Docker locally |
| 15 | `5-embed/local/2-start-embed-server.sh` | Start embed-server natively |
| 16 | `5-embed/local/3-run-pipeline.sh` | End-to-end local pipeline demo |

### Docker

| # | File / Directory | Description |
|---|---|---|
| 17 | `5-embed/docker/Dockerfile` | embed-server image (amd64 compatible) |
| 18 | `docker-compose.yml` | Add `qdrant` and `embed-server` services |
| 19 | `5-embed/docker/1-run-pipeline.sh` | End-to-end Docker pipeline demo |

### HPC

| # | File / Directory | Description |
|---|---|---|
| 20 | `5-embed/hpc/qdrant-serve-sbatch.sh` | SLURM service job for Qdrant |
| 21 | `5-embed/hpc/embed-serve-sbatch.sh` | SLURM service job for embedding worker |
| 22 | `5-embed/README.md` | Setup and usage for all three environments |

---

## Success Criteria

| Metric | Target |
|---|---|
| Recall@5 (synthetic queries) | > 0.80 across all 5 languages |
| Cross-language retrieval rate | > 0.70 (English query returns correct non-English video in top-5) |
| Embedding throughput | > 10 chunks/sec on a single GPU node |
| Qdrant query latency | < 100ms for top-5 search across 10,000 chunks |
| Graph renders correctly | All indexed videos appear as nodes with correct edges |
| Playlist generation | Returns > 0 results for any user with a defined role |

---

## Startup Sequence

**Local:**
```bash
bash 5-embed/local/1-start-qdrant.sh       # Qdrant via Docker
bash 5-embed/local/2-start-embed-server.sh # embed-server natively
ollama serve                               # Ollama (already exists)
bash 5-embed/local/3-run-pipeline.sh       # end-to-end demo
```

**Docker:**
```bash
docker compose up -d                       # starts qdrant + ollama + embed-server
bash 5-embed/docker/1-run-pipeline.sh      # end-to-end demo
```

**HPC (LUMI):**
```bash
# 1. Start Qdrant service
sbatch 5-embed/hpc/qdrant-serve-sbatch.sh

# 2. Start embedding worker (after Qdrant is running)
sbatch 5-embed/hpc/embed-serve-sbatch.sh

# 3. Start Ollama (already exists — for analyze.py + label.py)
sbatch 3-analyze/hpc/2-ollama-serve-sbatch.sh

# 4. Start file sync loop
sbatch 4-file-sync/hpc/sync-sbatch.sh

# 5. Start pipeline poller (processes new files through all 5 stages)
sbatch pipeline-hpc-poll.sh
```

---

## Phase 2 Backlog

- Fine-tune `xlm-roberta` on Llama 3 silver labels (SLURM GPU array, mirrors Stage 1 pattern)
- FastAPI service exposing `/search`, `/graph`, `/playlist` endpoints
- `playlist.html` and `graph.html` connected to live API
- RAG Chat UI — "Ask Slick+" with source-grounded timestamped answers
- Richer behavioural signals: replay rate, watch duration, Slack/Jira integrations
- Knowledge gap detection: identify topics with no coverage or low sentiment
- Impact Slick nudge: surface underviewed high-quality content
