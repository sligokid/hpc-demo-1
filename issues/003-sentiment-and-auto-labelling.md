## Parent PRD

`prd/task-2-company-brain/prd.md`

## What to build

Two related components that both live in `5-embed/` and operate on transcript chunks:

1. **`5-embed/sentiment.py`** — runs `cardiffnlp/twitter-xlm-roberta-base-sentiment` per chunk, aggregates to a per-video `sentiment_label` (positive / neutral / negative) and mean `sentiment_score`, stores both in the `video_metadata` Qdrant payload.
2. **`5-embed/label.py`** — calls the Ollama Llama 3 instance (already running for Stage 3) to label each chunk as positive / neutral / negative with domain context in the prompt, outputs `labels/<stem>.jsonl` JSONL training data for future fine-tuning.

Stage 4 (sentiment) is integrated into `pipeline.py` so it runs between Stage 3 (extract) and Stage 5 (embed).

See PRD: Sentiment Analysis section and Deliverables #4, #5.

## Acceptance criteria

- [ ] `python 5-embed/sentiment.py --transcript sync/output/<stem>/transcript.txt` outputs `sentiment_label` and `sentiment_score` to stdout
- [ ] After a full `pipeline.py` run, the `video_metadata` Qdrant point for the processed file has `sentiment_label` and `sentiment_score` populated
- [ ] `python 5-embed/label.py --transcripts sync/output/` produces at least one `.jsonl` file in `labels/` for each processed transcript
- [ ] Each JSONL line contains `chunk_text`, `label` (positive/neutral/negative), and `file` fields
- [ ] Sentiment label drives no individual performance scoring visible to managers (EU AI Act constraint)

## Blocked by

- Blocked by `issues/002-embed-server-and-search-local.md` (Qdrant `video_metadata` collection must exist to store sentiment payload)

## User stories addressed

- A floor manager sees that equipment safety content skews negative in sentiment across the Arabic-language library — flagging a potential knowledge gap (PRD Goal 3).
- Graph nodes are coloured by sentiment label — requires sentiment stored per video in Qdrant.
- `label.py` produces the JSONL training data needed for the deferred Phase 2 fine-tuning of `xlm-roberta`.
