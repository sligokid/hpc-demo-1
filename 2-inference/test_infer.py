"""
Tests for the transcribe() and transcribe_with_segments() functions in infer.py.

Mocks the HuggingFace pipeline so no real model weights or audio files are
needed. Asserts that the pipeline is called with the correct task/language
generate_kwargs and that the function returns a non-empty string.
"""

import numpy as np
from unittest.mock import MagicMock, patch

FAKE_AUDIO = (np.zeros(16000, dtype=np.float32), 16000)

FAKE_CHUNKS = [
    {"timestamp": (0.0, 2.5), "text": " hello"},
    {"timestamp": (2.5, 5.0), "text": " world"},
]


def make_mock_pipe(text="hello world"):
    mock_pipe = MagicMock(return_value={"text": text})
    return mock_pipe


def make_mock_pipe_with_chunks(text="hello world"):
    mock_pipe = MagicMock(return_value={"text": text, "chunks": FAKE_CHUNKS})
    return mock_pipe


@patch("infer.librosa.load", return_value=FAKE_AUDIO)
@patch("infer.pipeline")
def test_transcribe_task(mock_pipeline, _load):
    mock_pipeline.return_value = make_mock_pipe()

    from infer import transcribe

    result = transcribe("checkpoints/es", "audio.wav", task="transcribe")

    assert result and isinstance(result, str)
    _, kwargs = mock_pipeline.return_value.call_args
    assert kwargs["generate_kwargs"]["task"] == "transcribe"
    assert "language" not in kwargs["generate_kwargs"]


@patch("infer.librosa.load", return_value=FAKE_AUDIO)
@patch("infer.pipeline")
def test_translate_task(mock_pipeline, _load):
    mock_pipeline.return_value = make_mock_pipe()

    from infer import transcribe

    result = transcribe("checkpoints/es", "audio.wav", task="translate")

    assert result and isinstance(result, str)
    _, kwargs = mock_pipeline.return_value.call_args
    assert kwargs["generate_kwargs"]["task"] == "translate"
    assert "language" not in kwargs["generate_kwargs"]


@patch("infer.librosa.load", return_value=FAKE_AUDIO)
@patch("infer.pipeline")
def test_language_with_transcribe_task(mock_pipeline, _load):
    mock_pipeline.return_value = make_mock_pipe()

    from infer import transcribe

    result = transcribe("checkpoints/es", "audio.wav", language="spanish", task="transcribe")

    assert result and isinstance(result, str)
    _, kwargs = mock_pipeline.return_value.call_args
    assert kwargs["generate_kwargs"]["task"] == "transcribe"
    assert kwargs["generate_kwargs"]["language"] == "spanish"


@patch("infer.librosa.load", return_value=FAKE_AUDIO)
@patch("infer.pipeline")
def test_language_with_translate_task(mock_pipeline, _load):
    mock_pipeline.return_value = make_mock_pipe()

    from infer import transcribe

    result = transcribe("checkpoints/es", "audio.wav", language="spanish", task="translate")

    assert result and isinstance(result, str)
    _, kwargs = mock_pipeline.return_value.call_args
    assert kwargs["generate_kwargs"]["task"] == "translate"
    assert kwargs["generate_kwargs"]["language"] == "spanish"


@patch("infer.librosa.load", return_value=FAKE_AUDIO)
@patch("infer.pipeline")
def test_transcribe_with_segments_returns_text_and_segments(mock_pipeline, _load):
    mock_pipeline.return_value = make_mock_pipe_with_chunks()

    from infer import transcribe_with_segments

    text, segments = transcribe_with_segments("checkpoints/es", "audio.wav")

    assert text == "hello world"
    assert len(segments) == 2
    assert segments[0] == {"start": 0.0, "end": 2.5, "text": " hello"}
    assert segments[1] == {"start": 2.5, "end": 5.0, "text": " world"}


@patch("infer.librosa.load", return_value=FAKE_AUDIO)
@patch("infer.pipeline")
def test_transcribe_with_segments_drops_none_end_timestamp(mock_pipeline, _load):
    """Last chunk has None end timestamp (audio cut off mid-word) — must not raise."""
    chunks_with_none = FAKE_CHUNKS + [{"timestamp": (5.0, None), "text": " cut"}]
    mock_pipeline.return_value = MagicMock(
        return_value={"text": "hello world cut", "chunks": chunks_with_none}
    )

    from infer import transcribe_with_segments

    text, segments = transcribe_with_segments("checkpoints/es", "audio.wav")

    assert len(segments) == 2  # None-end chunk dropped
    assert all(s["end"] is not None for s in segments)


@patch("infer.librosa.load", return_value=FAKE_AUDIO)
@patch("infer.pipeline")
def test_transcribe_with_segments_uses_return_timestamps(mock_pipeline, _load):
    mock_pipeline.return_value = make_mock_pipe_with_chunks()

    from infer import transcribe_with_segments

    transcribe_with_segments("checkpoints/es", "audio.wav")

    _, pipe_kwargs = mock_pipeline.call_args
    assert pipe_kwargs["return_timestamps"] is True
