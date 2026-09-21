"""
Tests for sentiment.py.

The HuggingFace pipeline is mocked so no model weights or GPU are required.
"""

import sys
import pathlib
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(pathlib.Path(__file__).parent))

import sentiment as sent_mod


# ---------------------------------------------------------------------------
# _split_text
# ---------------------------------------------------------------------------

def test_split_text_single_chunk_short():
    text = "Hello world. This is a test."
    chunks = sent_mod._split_text(text)
    assert len(chunks) == 1
    assert "Hello world" in chunks[0]


def test_split_text_splits_long_text():
    # Build a text of ~600 words (3x the 200-word chunk limit)
    sentence = "This is a sentence with ten words in it here. "
    text = sentence * 60
    chunks = sent_mod._split_text(text)
    assert len(chunks) >= 3
    for chunk in chunks:
        assert len(chunk.split()) <= sent_mod._CHUNK_WORDS + 20  # some slack for last sentence


def test_split_text_empty_string():
    chunks = sent_mod._split_text("")
    assert chunks == [""]


# ---------------------------------------------------------------------------
# run_sentiment — mocked classifier
# ---------------------------------------------------------------------------

def _make_clf(label: str, score: float):
    """Return a mock HF pipeline that always returns (label, score)."""
    mock_clf = MagicMock()
    mock_clf.return_value = [[{"label": label, "score": score}]]
    return mock_clf


@pytest.fixture(autouse=True)
def reset_classifier():
    """Reset the module-level singleton between tests."""
    sent_mod._classifier = None
    yield
    sent_mod._classifier = None


def test_run_sentiment_positive_chunks():
    with patch.object(sent_mod, "_get_classifier",
                      return_value=_make_clf("positive", 0.9)):
        result = sent_mod.run_sentiment(["Great work!", "Amazing result!"])

    assert result["sentiment_label"] == "positive"
    assert result["sentiment_score"] > 0


def test_run_sentiment_negative_chunks():
    with patch.object(sent_mod, "_get_classifier",
                      return_value=_make_clf("negative", 0.8)):
        result = sent_mod.run_sentiment(["Terrible failure.", "Very bad outcome."])

    assert result["sentiment_label"] == "negative"
    assert result["sentiment_score"] < 0


def test_run_sentiment_neutral_chunks():
    with patch.object(sent_mod, "_get_classifier",
                      return_value=_make_clf("neutral", 0.7)):
        result = sent_mod.run_sentiment(["The procedure has five steps."])

    assert result["sentiment_label"] == "neutral"
    assert result["sentiment_score"] == 0.0


def test_run_sentiment_accepts_segment_dicts():
    segments = [
        {"text": "Well done!", "start": 0.0, "end": 2.0},
        {"text": "Excellent work.", "start": 2.0, "end": 4.0},
    ]
    with patch.object(sent_mod, "_get_classifier",
                      return_value=_make_clf("positive", 0.95)):
        result = sent_mod.run_sentiment(segments)

    assert result["sentiment_label"] == "positive"


def test_run_sentiment_empty_list():
    result = sent_mod.run_sentiment([])
    assert result == {"sentiment_label": "neutral", "sentiment_score": 0.0}


def test_run_sentiment_score_is_rounded():
    with patch.object(sent_mod, "_get_classifier",
                      return_value=_make_clf("positive", 0.123456789)):
        result = sent_mod.run_sentiment(["Good."])

    # score is rounded to 4 decimal places
    assert result["sentiment_score"] == round(result["sentiment_score"], 4)


def test_run_sentiment_majority_label_wins():
    """Two positive chunks and one negative — label should be positive."""
    call_count = 0
    responses = [
        [{"label": "positive", "score": 0.9}],
        [{"label": "positive", "score": 0.85}],
        [{"label": "negative", "score": 0.8}],
    ]

    mock_clf = MagicMock()
    mock_clf.side_effect = responses

    with patch.object(sent_mod, "_get_classifier", return_value=mock_clf):
        result = sent_mod.run_sentiment(["Good.", "Great.", "Bad."])

    assert result["sentiment_label"] == "positive"
