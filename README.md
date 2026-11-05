# SLICK+ HPC — The Video First Company Brain
HPC-Enhanced Generative AI Agent for Hyper-Personalized Knowledge Sharing in Large Enterprises.

**Goal: Turning speech & video into machine-readable knowledge at HPC scale.**

## What this is

An end-to-end, unattended HPC pipeline that transforms short-form video and audio into machine-readable organisational knowledge. It runs on [LUMI](https://www.lumi-supercomputer.eu/) with no manual babysitting: a self-resubmitting SLURM job (`pipeline-hpc-poll.sh`) wakes every 10 minutes, picks up new files that arrived from Google Drive, and submits a SLURM array job covering eleven pipeline stages:

**1-train** fine-tunes Whisper on Google FLEURS; **2-inference** transcribes audio; **3-analyze** extracts metadata via LLM; **4-file-sync** syncs files between Google Drive and LUMI Lustre scratch; **5-sentiment** scores tone per chunk; **6-embed** encodes transcripts into 1024-dim vectors; **7-index** writes vectors to Qdrant; **8-search** provides semantic retrieval; **9-graph** builds a knowledge graph and generates playlists; **10-agent** runs a LangGraph conversational agent; **11-sop/teleprompter** converts transcripts into SOPs and presenter scripts.

The pipeline supports five languages: **en, es, fr, zh-CN, ar** (see [Supported Languages](#supported-languages)). Google Drive is the human-facing surface for uploading input and downloading output; LUMI Lustre scratch (`sync/`) is the working store; Qdrant is the queryable vector index. Each language is fine-tuned independently as a separate SLURM job — no shared multilingual model, no serialisation. See per-stage READMEs and the [Data Pipeline Overview](#data-pipeline-overview) for full details.

## Supported Languages

| Language | Code | FLEURS Locale | Checkpoint Path |
|---|---|---|---|
| English | en | en_us | checkpoints/en |
| Spanish | es | es_419 | checkpoints/es |
| French | fr | fr_fr | checkpoints/fr |
| Mandarin | zh-CN | cmn_hans_cn | checkpoints/zh-CN |
| Arabic | ar | ar_eg | checkpoints/ar |

> **Note:** `pipeline.yaml` currently uses `zh` for the Mandarin language code — this is a known inconsistency with the training scripts and checkpoint paths (which use `zh-CN`). Full resolution requires fixes to `pipeline.yaml`, `pipeline.py`, and input directory naming; that work is tracked separately and is not addressed in this README update.

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
9. How do we turn captured video knowledge into reusable procedures (SOP) and presenter-ready scripts (Teleprompter)?

## Solution
1. Fine-tune `openai/whisper` for multiple languages using Google FLEURS dataset on HPC
2. Inference pipeline transforming video to transcript using fine-tuned speech recognition models.
3. Feature extraction from transcript (title, description, tags, goals, and skills) via LLM.
4. Cloud to HPC transfer pipeline for data transfer and governance via rclone.
5. Sentiment analysis over chunks of video to form an average sentiment score.
6. A searchable Vector database of knowledge for similarity search, clustering, and drill-down/aggregation.
7. An interactive knowlege graph to show relationships between videos.
8. A RAG based chat agent that can answer questions about the video knowledge base.
9. SOP file generation extracts structured operating procedures from transcripts + analysis; Teleprompter file generation converts any SOP into speech-optimised presenter scripts.

## Example use cases

### Feature Extraction, Auto Tagging

*video ──▶ feature files*

Upload a library of internal how-to videos. The pipeline transcribes, and extracts metadata and features such as title, description, tags, goals, and skills via LLM. The results are written to files:

- `<stem>.transcript.txt`
- `<stem>.analysis.json`

Results can be used in Slick+ for video metadata enrichment.

### Video to SOP

*video ──▶ SOP document*

An AI workflow that takes a recorded video as source material and produces a structured SOP within 15 minutes. The SOP is a text, Word, or PDF file.

- `<stem>.sop.md`
- `<stem>.sop.pdf`

---

### Voice-only to SOP

*audio ──▶ SOP document*

An AI workflow that turns a recorded discussion between colleagues (with no video) into an SOP.

- `<stem>.sop.md`
- `<stem>.sop.pdf`

---

### SOP to video script

*SOP document ──▶ video script*

The reverse direction: taking an existing written SOP and converting it into a short video script, with AI doing the drafting. A subject-matter expert would review the script before anything is recorded. 

Ideally, the review step is built into the flow rather than left as an afterthought. (WIP)

- `<stem>.teleprompter.md`

### Global workforce — any language, one knowledge base

*multilingual video ──▶ single searchable knowledge base*

Employees record in Spanish, French, Arabic, or Mandarin and upload as-is. Every video is transcribed, translated, and indexed into one shared knowledge base — no human translation, no duplicate effort per language.

- `<stem>.transcript.txt`
- `<stem>.analysis.json`

### See your company's knowledge as a map

*indexed knowledge base ──▶ interactive graph*

Open one HTML file and see every video as a node. Related topics cluster together, gaps are immediately visible, and negative-sentiment content is flagged in red.

- `graph.html` (interactive knowledge graph)

### Compliance and audit trails

*knowledge graph ──▶ coverage report*

Tag all videos with goals and skills at ingest time. Use the knowledge graph to verify that required training topics are covered, identify gaps, and export a visualisation for auditors.

- `graph.html` (interactive knowledge graph)

### Spot tone problems before they spread

*video ──▶ sentiment score*

The pipeline scores tone chunk-by-chunk before a video is shared. A frustrated rant, safety complaint, or off-message recording is flagged automatically — no one has to watch it first.

- `<stem>.analysis.json` (includes per-chunk sentiment labels and scores)

---

## Agentic use cases *(Experimental — Agent is local to LUMI)*

### Onboarding a new hire

*video library ──▶ agent Q&A*

A new hire asks the agent questions in natural language — *"How do we fix a broken down printer?"* — and gets cited answers with timestamps, without watching every video.

- Cited video list with source timestamps.

---

### Personalised learning playlists

*role profile ──▶ curated playlist*

A manager asks the agent to *"create an intro to Slick+ playlist for a new hire in sales"*. The agent retrieves relevant chunks, ranks them by role relevance, and presents a draft for human approval before saving.

- Draft playlist with manager approval gate

---

## Data Pipeline Overview

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 1 · TRAINING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Google FLEURS  ──▶  SLURM GPU array (1 job / lang)  ──▶  checkpoints/<lang>/
                      en · es · fr · zh-CN · ar              fine-tuned Whisper

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 2 · INGESTION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  [Upload audio]  ──▶  Google Drive        ──▶  rclone  ──▶  LUMI sync/input/
  mp3/mp4/wav/flac      whisper-sync/input/      5 min         poll 10 min
                                                                     │
                                                                     ▼
                                                          pipeline-hpc-submit.sh

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 3 · INFERENCE  
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  TRANSCRIBE ──▶ ANALYSE ──▶ SENTIMENT ──▶ EMBED ──▶ INDEX (Qdrant)
  stage 2        stage 3      stage 5      stage 6   stage 7│
                                                            │
                               ┌──────────────┬────────────┘
                               │              │              │
                               ▼              ▼              ▼
                            SEARCH          GRAPH          AGENT
                           stage 8         stage 9        stage 10
                           search.py       graph.py       agent.py
                                         playlist.py    (LangGraph)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  4 · AGENT  (Experimental — runs locally on LUMI)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  user question  ──▶  LangGraph agent  ──▶  answer / playlist / summary
                       Qwen · stage 10       cited sources + timestamps
                       agent.py              human approval gate (artefacts)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  5 · SOP  
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  transcript + analysis  ──▶  SOP
                               Qwen · stage 11a
                               .sop.md · .sop.pdf

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  6 · TELEPROMPTER  
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  any .sop.md / .txt / .pdf / .docx  ──▶  TELEPROMPTER SCRIPT
                                           Qwen · stage 11b
                                           .teleprompter.md

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  7 · OUTPUT SYNC
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  LUMI sync/output/  ──▶  rclone  ──▶  Google Drive whisper-sync/output/
  .transcript.txt          5 min
  .segments.json
  .analysis.json
  .sop.md 
  .sop.pdf
  .teleprompter.md
  graph.html

```

---

## Models Used in the Pipeline

| Variable / Config | Model | Stage | Role |
|---|---|---|---|
| `MODEL_ID` | `openai/whisper-small` | 1-train / 2-inference | Fine-tuned ASR — transcription and ES→EN translation |
| `SENTIMENT_MODEL` | `cardiffnlp/twitter-roberta-base-sentiment-latest` | 5-sentiment | Per-chunk sentiment label and score |
| `EMBED_MODEL` | `intfloat/multilingual-e5-large` | 6-embed / 8-search / 10-agent | Text embedding — 1024-dim L2-normalised vectors |
| `GENERATE_MODEL` | `llama3:latest` | 3-analyze / 10-agent | Metadata extraction (title, description, tags, goals, skills); `generate_summary` / `generate_playlist` |
| `AGENT_MODEL` | `qwen2.5:7b` | 10-agent | LangGraph tool-calling and reasoning |
| `sop.model` | `qwen2.5:7b` | 11-sop | SOP generation from transcript + analysis |
| `teleprompter.model` | `qwen2.5:7b` | 11-sop | Teleprompter script generation from any SOP document |

## Development

See [DEVELOPMENT.md](DEVELOPMENT.md) for local setup, Docker, HPC launch instructions, and testing. Manifest file behaviour is documented in the [Manifest files](#manifest-files) section below.

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
| [`11-sop/`](11-sop/README.md) | SOP & Teleprompter generation — `sop.py` produces `.sop.md` + `.sop.pdf` from transcript + analysis; `teleprompter.py` converts any SOP into a speech-optimised presenter script (`.teleprompter.md`) |
| [`pipeline.py`](pipeline.py) | End-to-end orchestrator: infer → analyze → sentiment → embed → index → sop |
| [`pipeline.yaml`](pipeline.yaml) | Central configuration (model, server URLs, feature flags) |
| `pipeline-local.sh` | Run full pipeline locally with native Python and Ollama |
| `pipeline-docker.sh` | Run full pipeline inside Docker Compose |
| `pipeline-hpc-submit.sh` | Scan manifest and submit SLURM array jobs |
| `pipeline-hpc-sbatch.sh` | SLURM GPU task wrapper — runs `pipeline.py` inside Singularity |
| `pipeline-hpc-poll.sh` | Self-resubmitting scheduler — polls for new files every 10 minutes |
| `profiles/<user>.json` | Per-user profile for playlist personalisation |
| `roles.yaml` | Role → tag mapping used by `9-graph/playlist.py` |



## Manifest files

Two manifest files are written during each cycle; they serve different purposes and must not be confused.

| File | Written by | Read by | Purpose |
|---|---|---|---|
| `logs/sync-manifest.txt` | `4-file-sync/sync.sh` | `sync.sh` (idempotency check), test scripts | Audit log of every file that has ever arrived from Google Drive. `sync.sh` appends new filenames on each inbound cycle and uses the list to avoid recording the same filename twice in the manifest. **The pipeline never reads this file.** |
| `logs/pipeline-manifest-<ts>.txt` | `pipeline-hpc-submit.sh` | SLURM array jobs | Per-cycle work list, built by re-globbing `sync/input/` directly at submit time. This is the file the SLURM array actually processes each cycle. Because the manifest is regenerated from the filesystem every cycle, any file still present in `sync/input/` will be resubmitted on subsequent cycles — permanently failing files are never automatically retired (see [issues/013.md](issues/013.md)). |

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