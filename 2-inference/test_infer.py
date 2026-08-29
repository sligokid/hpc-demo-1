"""
Tests for the transcribe() function in infer.py.

Mocks the HuggingFace pipeline so no real model weights or audio files are
needed. Asserts that the pipeline is called with the correct task/language
generate_kwargs and that the function returns a non-empty string.
"""

import numpy as np
from unittest.mock import MagicMock, patch

FAKE_AUDIO = (np.zeros(16000, dtype=np.float32), 16000)


def make_mock_pipe(text="hello world"):
    mock_pipe = MagicMock(return_value={"text": text})
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
