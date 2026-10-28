# SLICK+ HPC — The Video First Company Brain
HPC-Enhanced Generative AI Agent for Hyper-Personalized Knowledge Sharing in Large Enterprises.

**Goal: Turning speech & video into machine-readable knowledge at HPC scale.**

## How work really gets done

This experiment aims to validate and scale a new generative AI module that transforms internal tacit knowledge, captured through short-form video, into hyper-personalized, real-time learning content tailored to each employee’s role, behavior, and moment-of-need. The core innovation lies in combining generative AI, multilingual transcription, and behavioral personalization to address a persistent problem in large, distributed workplaces: the loss, inaccessibility, and underutilization of institutional know-how. Traditional learning management systems fail to capture informal insights and peer knowledge that are critical for onboarding, retention, and productivity. 

People first. AI assisted. Searchable by default. Structured for managers. Ready for agents later.

## Problem? 
1. Training a speech recognition model from scratch for multiple languages is prohibitively expensive and slow. 
2. Transcription & Translation using fine-tuned checkpoints requires open source, open weight models.
3. Summarisation and Categorisation of video content at scale is challenging.
4. Data sovereignty, data governance and secure transferral of data between cloud and HPC is a priority. 
5. Sentiment of a video often fluctuates throughout the video, and a single score does not capture the full picture.
6. How can we group, index, search, retrieve and rank videos in a way that is useful for business users?
7. How are all the videos related to each other?
8. How can we have a conversation with our video knowledge base ?


## Solution
1. Fine-tune `openai/whisper` for multiple languages using Google FLEURS dataset on HPC
2. Inference pipeline transformimg video to transcript using fine-tuned speech recognition models.
3. Feature extraction from transcript (title, description, tags, goals, and skills) via LLM.
4. Cloud to HPC transfer pipeline for data transfer and governance via rclone.
5. Sentiment analysis over chunks of video to form an average sentiment score.
6. A searchable Vector database ok knowledge for similarity search, clustering, and drill-down/aggregation.
7. An interactive knowlege graph to show relationships between videos.
8. A RAG based chat agent that can answer questions about the video knowledge base.

## Example Agent interactions

**Factual search** (`search_knowledge_base`):
```
> What is Slick+ and how does it work?
```

**Creator / title lookup** (`search_knowledge_base` → `get_video_metadata`):
```
> Which video features Linda Hegarty and what are the key topics?
```

**Full transcript** (`get_full_transcript`):
```
> Give me the full transcript of the Slick+ intro video
```

**Summary Generation** (`generate_summary`):
```
> Create a summary of the Slick+ intro video
```

**Playlist Generation** (`generate_playlist`):
```
> Create a Into to Slick Playlist for a new hire
```

**Multi-hop** (agent calls multiple tools autonomously):
```
> What are the main topics covered in the AI videos and who are the speakers?
```

---

## Pipeline Overview

```
  ┌──────────────────────────────────────────────────────────────────────────┐
  │                          STAGE 1: TRAINING                               │
  │  Fine-tune openai/whisper-small on Google FLEURS                         │
  │  en · es · fr · zh-CN · ar  (5 parallel SLURM GPU jobs)                  │
  └──────────────────────────────┬───────────────────────────────────────────┘
                                 │  checkpoints/<lang>/
                                 ▼
─────────────────────────────────────────────────────────────────────────────

  ┌──────────────────┐
  │   Google Drive   │◄── [ Upload mp3 / mp4 / wav / flac / m4a / ogg ]
  │ whisper-sync/    │
  │   input/         │
  └────────┬─────────┘
           │  rclone (C-sync · every 5 min)
           ▼
  ┌──────────────────┐
  │  LUMI HPC        │
  │   sync/input/    │
  └────────┬─────────┘
           │  Z-poll (every 10 min) → pipeline-hpc-submit.sh → SLURM array
           ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │                        STAGE 2: TRANSCRIBE                               │
  │  infer.py — Whisper (AMD/ROCm GPU, fine-tuned checkpoint)                │
  │  Chunked 30s windows · any-length audio · 5-second overlap               │
  └──────────────────────────────┬───────────────────────────────────────────┘
                                 │  sync/output/<lang>/<stem>.transcript.txt
                                 │                         .segments.json
                                 ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │                         STAGE 3: ANALYSE                                 │
  │  analyze.py — Llama 3 via Ollama (B-ollama GPU daemon)                   │
  │  Extracts: title · description · tags · goals · skills                   │
  └──────────────────────────────┬───────────────────────────────────────────┘
                                 │  sync/output/<lang>/<stem>.analysis.json
                                 ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │                        STAGE 5: SENTIMENT                                │
  │  sentiment.py — cardiffnlp/twitter-roberta-base-sentiment-latest         │
  │  Majority-vote label + signed mean score across transcript chunks        │
  └──────────────────────────────┬───────────────────────────────────────────┘
                                 │  { sentiment_label, sentiment_score }
                                 ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │                          STAGE 6: EMBED                                  │
  │  embed_server.py — intfloat/multilingual-e5-large (D-embed · port 8765)  │
  │  Encodes transcript chunks → 1024-dim L2-normalised vectors              │
  └──────────────────────────────┬───────────────────────────────────────────┘
                                 │  { vectors: [{text, ts_start, ts_end, vector}] }
                                 ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │                          STAGE 7: INDEX                                  │
  │  index_server.py — Flask (F-index · port 8766)                           │
  │  Writes chunk vectors → Qdrant video_chunks                              │
  │  Writes video metadata → Qdrant video_metadata  (E-qdrant · port 6333)   │
  └──────────────────────────────┬───────────────────────────────────────────┘
                                 │  sync/output/<lang>/<stem>.analysis.json
                                 │                         .transcript.txt
                                 ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │                        STAGE 11: SOP                                     │
  │  sop.py — Qwen 2.5 via Ollama                                            │
  │  Generates a Standard Operating Procedure from transcript + analysis     │
  └──────────────────────────────┬───────────────────────────────────────────┘
                                 │  sync/output/<lang>/<stem>.sop.md
                                 │                         .sop.pdf
                                 ▼
                    ┌────────────┴──────────┬──────────────────────┐
                    ▼                       ▼                      ▼
  ┌──────────────────────┐  ┌───────────────────────────┐  ┌───────────────────────────┐
  │   STAGE 8: SEARCH    │  │      STAGE 9: GRAPH       │  │     STAGE 10: AGENT       │
  │  search.py           │  │  graph.py — knowledge     │  │  agent.py — LangGraph     │
  │  Semantic nearest-   │  │  graph (nodes/edges)      │  │  conversational agent     │
  │  neighbour lookup    │  │  playlist.py — ranked     │  │  Factual Q&A, summaries,  │
  │  over video_chunks   │  │  personalised playlist    │  │  playlists with human     │
  │                      │  │  (G-graph)                │  │  approval gate            │
  └──────────────────────┘  └───────────────────────────┘  └───────────────────────────┘
                                 │
           rclone (C-sync · every 5 min)
                                 ▼
  ┌──────────────────┐
  │   Google Drive   │◄── sync/output/ (transcripts · analysis · graph.html)
  │ whisper-sync/    │
  │   output/        │
  └──────────────────┘
```

> **Note:** Stage 4 (file sync) is the background rclone loop — not an inline processing stage. It feeds `sync/input/` and drains `sync/output/` independently on a 5-minute cycle.

---

## Models Used in the Pipeline

| Variable / Config | Model | Stage | Role |
|---|---|---|---|
| `MODEL_ID` | `openai/whisper-small` | 1-train / 2-inference | Fine-tuned ASR — transcription and ES→EN translation |
| `SENTIMENT_MODEL` | `cardiffnlp/twitter-roberta-base-sentiment-latest` | 5-sentiment | Per-chunk sentiment label and score |
| `EMBED_MODEL` | `intfloat/multilingual-e5-large` | 6-embed / 8-search / 10-agent | Text embedding — 1024-dim L2-normalised vectors |
| `GENERATE_MODEL` | `llama3:latest` | 3-analyze / 10-agent | Metadata extraction (title, description, tags, goals, skills); `generate_summary` / `generate_playlist` |
| `AGENT_MODEL` | `qwen2.5:3b` | 10-agent | LangGraph tool-calling and reasoning |
| `sop.model` | `qwen2.5:7b` | 11-sop | SOP generation from transcript + analysis |

## Development

See [DEVELOPMENT.md](DEVELOPMENT.md) for local setup, Docker, HPC launch instructions, testing, and monitoring.

## Repository Structure

| Directory / File | Description |
|---|---|
| [`1-train/`](1-train/README.md) | Whisper fine-tuning on FLEURS — SLURM GPU array, 1 job per language |
| [`2-inference/`](2-inference/README.md) | Chunked long-form audio transcription and ES→EN translation |
| [`3-analyze/`](3-analyze/README.md) | Structured metadata extraction via Llama 3 / Ollama |
| [`4-file-sync/`](4-file-sync/README.md) | Google Drive ↔ LUMI bi-directional rclone sync (5-min polling loop) |
| [`5-sentiment/`](5-sentiment/README.md) | Per-video sentiment label and score from transcript chunks |
| [`6-embed/`](6-embed/README.md) | Embedding server — `POST /embed` returns 1024-dim vectors (port 8765) |
| [`7-index/`](7-index/README.md) | Index server — `POST /index` and `POST /metadata` write to Qdrant (port 8766) |
| [`8-search/`](8-search/README.md) | Semantic nearest-neighbour search over indexed transcript chunks |
| [`9-graph/`](9-graph/README.md) | Knowledge graph builder and personalised playlist generator |
| [`10-agent/`](10-agent/README.md) | LangGraph conversational agent — factual Q&A, summaries, playlists with human approval gate |
| [`11-sop/`](11-sop/local/README.md) | SOP generator — produces `.sop.md` and `.sop.pdf` from transcript + analysis via Qwen 2.5 |
| [`pipeline.py`](pipeline.py) | End-to-end orchestrator: infer → analyze → sentiment → embed → index → sop |
| [`pipeline.yaml`](pipeline.yaml) | Central configuration (model, server URLs, feature flags) |
| `pipeline-local.sh` | Run full pipeline locally with native Python and Ollama |
| `pipeline-docker.sh` | Run full pipeline inside Docker Compose |
| `pipeline-hpc-submit.sh` | Scan manifest and submit SLURM array jobs |
| `pipeline-hpc-sbatch.sh` | SLURM GPU task wrapper — runs `pipeline.py` inside Singularity |
| `pipeline-hpc-poll.sh` | Self-resubmitting scheduler — polls for new files every 10 minutes |
| `profiles/<user>.json` | Per-user profile for playlist personalisation |
| `roles.yaml` | Role → tag mapping used by `9-graph/playlist.py` |



## References

- [HuggingFace: Fine-Tune Whisper](https://huggingface.co/blog/fine-tune-whisper)
- [Google FLEURS Dataset](https://huggingface.co/datasets/google/fleurs)
- [intfloat/multilingual-e5-large](https://huggingface.co/intfloat/multilingual-e5-large)
- [cardiffnlp/twitter-roberta-base-sentiment-latest](https://huggingface.co/cardiffnlp/twitter-roberta-base-sentiment-latest)
- [Ollama Documentation](https://github.com/ollama/ollama)
- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [rclone Documentation](https://rclone.org/drive/)

---
## Acknowledgements

- This work was supported by the FFplus project, funded by the European High-Performance Computing Joint Undertaking (EuroHPC JU) under grant agreement No 101163317.
- We acknowledge the EuroHPC Joint Undertaking for awarding us access to LUMI, hosted at CSC (IT Center for Science) Kajaani, Finland, under project ID project_465003359.