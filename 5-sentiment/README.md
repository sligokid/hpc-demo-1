# 5-sentiment — Sentiment Analysis

Classifies overall video tone before content reaches the vector database. Runs `cardiffnlp/twitter-roberta-base-sentiment-latest` over transcript chunks and aggregates to a per-video `sentiment_label` and `sentiment_score` that are stored in the `video_metadata` Qdrant collection.

---

## Files

| File | Description |
|---|---|
| `sentiment.py` | HuggingFace sentiment classifier — aggregates per-chunk labels to a video-level score |
| `test_sentiment.py` | Unit tests for `sentiment.py` (HuggingFace pipeline mocked) |

---

## How it works

**Chunking:** The transcript is split on sentence boundaries into ~200-word windows. Whisper segment dicts (with a `text` key) are accepted directly — no re-splitting needed when segments come from `2-inference/infer.py`.

**Classification:** Each chunk is truncated to 400 characters and passed to the HuggingFace pipeline. The model returns a label and a confidence score for each.

**Aggregation — two outputs:**

| Output | How it is computed |
|---|---|
| `sentiment_label` | Majority vote across all chunks — the label that appears most often wins |
| `sentiment_score` | Mean of signed polarity scores: positive chunks contribute `+score`, negative chunks contribute `−score`, neutral chunks contribute `0`. Range is `[−1.0, 1.0]`, rounded to 4 decimal places. |

**Device selection:** CUDA → Apple Silicon MPS → CPU, checked automatically on first call. The classifier is a module-level singleton — it is loaded once per process regardless of how many files are processed.

---

## Standalone usage

```bash
python 5-sentiment/sentiment.py --transcript sync/output/en/my-video.transcript.txt
# {"sentiment_label": "positive", "sentiment_score": 0.72}
```

---

## Pipeline integration

`pipeline.py` imports `run_sentiment` and `_split_text` directly and calls them between the Analyze and Embed stages:

```
Infer → Analyze → Sentiment → Embed (6-embed) → Index (7-index)
```

The result dict (`sentiment_label`, `sentiment_score`) is merged into the analysis metadata before it is forwarded to the index server, so both fields end up in the `video_metadata` Qdrant collection alongside title, tags, and description.

Enable in `pipeline.yaml`:

```yaml
sentiment:
  enabled: true
```

---

## Limitations

**General-purpose model.** `twitter-roberta-base-sentiment-latest` was trained on tweets, not L&D transcripts. Corporate safety language ("isolate before re-energising") reads as neutral even when it is describing a critical risk. The majority-vote aggregation amplifies this: a video that is 70% factual procedure and 30% serious warnings will almost certainly be labelled `neutral`.

**Chunk boundaries ignore semantic coherence.** Splitting on sentence boundaries at a fixed word count can cut a single thought across two chunks, diluting the signal for both. Whisper segment dicts (which correspond to actual speech pauses) produce more natural boundaries — use `embed_enabled: true` in `pipeline.yaml` to pass segments rather than plain text.

**`sentiment_score` is not a probability.** It is a signed weighted mean that compresses all per-chunk signals into a single scalar. A score of `0.3` could mean every chunk scored mildly positive, or half the chunks scored strongly positive and half scored strongly negative. The distribution of chunk-level scores is not stored.

---

## Tests

```bash
pytest 5-sentiment/ -v
```

No GPU, model weights, or external services required — the HuggingFace pipeline is mocked throughout.
