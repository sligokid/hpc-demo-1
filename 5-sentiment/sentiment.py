"""
Sentiment analysis: runs cardiffnlp/twitter-roberta-base-sentiment-latest per chunk,
aggregates to per-video sentiment_label (positive/neutral/negative) and mean
sentiment_score (signed polarity in [-1, 1]), stores both in the video_metadata
Qdrant payload via the embed server /metadata endpoint.

Usage (standalone):
    python 5-embed/sentiment.py --transcript sync/output/en/<stem>.transcript.txt

Output (stdout):
    {"sentiment_label": "positive", "sentiment_score": 0.72}
"""

import argparse
import json
import re
import sys
from collections import Counter

from transformers import pipeline as hf_pipeline

SENTIMENT_MODEL = "cardiffnlp/twitter-roberta-base-sentiment-latest"

# Signed weight for polarity score: positive=+1, neutral=0, negative=-1
# twitter-roberta-base-sentiment-latest returns labels as plain strings
# ("positive"/"neutral"/"negative") rather than LABEL_0/1/2, so no mapping needed.
_POLARITY = {"positive": 1.0, "neutral": 0.0, "negative": -1.0}

_CHUNK_WORDS = 200   # ~150 tokens, well within the 512-token model limit

_classifier = None


def _get_classifier():
    global _classifier
    if _classifier is None:
        import torch
        if torch.cuda.is_available():
            device = 0          # CUDA — HPC GPU nodes and NVIDIA desktops
        elif torch.backends.mps.is_available():
            device = "mps"      # Apple Silicon GPU
        else:
            device = -1         # CPU fallback
        _classifier = hf_pipeline(
            "text-classification",
            model=SENTIMENT_MODEL,
            top_k=1,
            device=device,
        )
    return _classifier


def _split_text(text: str) -> list:
    """Split plain text into ~200-word chunks on sentence boundaries."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    chunks, current, current_len = [], [], 0
    for sent in sentences:
        words = sent.split()
        if current_len + len(words) > _CHUNK_WORDS and current:
            chunks.append(" ".join(current))
            current, current_len = words, len(words)
        else:
            current.extend(words)
            current_len += len(words)
    if current:
        chunks.append(" ".join(current))
    return chunks or [text]


def run_sentiment(chunks) -> dict:
    """
    Compute aggregate sentiment over a list of chunks.

    Args:
        chunks: list of str, or list of dicts with a 'text' key (Whisper segments).

    Returns:
        {"sentiment_label": str, "sentiment_score": float}
        sentiment_score is a signed polarity mean in [-1.0, 1.0].
    """
    texts = [c["text"] if isinstance(c, dict) else c for c in chunks]
    # Truncate each chunk to 400 chars to avoid tokenizer truncation warnings
    texts = [t[:400] for t in texts if t.strip()]
    if not texts:
        return {"sentiment_label": "neutral", "sentiment_score": 0.0}

    clf = _get_classifier()
    results = clf(texts)

    labels = []
    polarity_scores = []
    for res in results:
        entry = res[0] if isinstance(res, list) else res
        label = entry["label"].lower()
        labels.append(label)
        polarity_scores.append(_POLARITY[label] * entry["score"])

    agg_label = Counter(labels).most_common(1)[0][0]
    agg_score = round(sum(polarity_scores) / len(polarity_scores), 4)

    return {"sentiment_label": agg_label, "sentiment_score": agg_score}


def main():
    parser = argparse.ArgumentParser(
        description="Run sentiment analysis on a transcript file."
    )
    parser.add_argument(
        "--transcript",
        required=True,
        metavar="FILE",
        help="Path to transcript .txt file.",
    )
    args = parser.parse_args()

    with open(args.transcript) as f:
        text = f.read()

    if not text.strip():
        print("Error: transcript is empty.", file=sys.stderr)
        sys.exit(1)

    chunks = _split_text(text)
    result = run_sentiment(chunks)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
