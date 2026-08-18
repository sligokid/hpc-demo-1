"""
Tests for the transcribe() function in infer.py.

Mocks WhisperProcessor and WhisperForConditionalGeneration so no real
model weights are loaded. Asserts that get_decoder_prompt_ids() is called
with the correct task argument and that the function returns a non-empty string.
"""

import numpy as np
from unittest.mock import MagicMock, patch
import torch
import pytest

FAKE_AUDIO = (np.zeros(16000, dtype=np.float32), 16000)


def make_mocks():
    """Return a (mock_processor, mock_model) pair wired up for transcribe()."""
    mock_processor = MagicMock()
    mock_processor.return_value.input_features = torch.zeros(1, 80, 3000)
    mock_processor.get_decoder_prompt_ids.return_value = [[1, 2], [3, 4]]
    mock_processor.batch_decode.return_value = ["hello world"]

    mock_model = MagicMock()
    mock_model.return_value.to.return_value = mock_model.return_value
    mock_model.return_value.generate.return_value = torch.tensor([[1, 2, 3]])

    return mock_processor, mock_model


@patch("infer.librosa.load", return_value=FAKE_AUDIO)
@patch("infer.WhisperForConditionalGeneration")
@patch("infer.WhisperProcessor")
def test_transcribe_task(mock_proc_cls, mock_model_cls, _load):
    mock_processor, mock_model = make_mocks()
    mock_proc_cls.from_pretrained.return_value = mock_processor
    mock_model_cls.from_pretrained.return_value = mock_model.return_value

    from infer import transcribe

    result = transcribe("checkpoints/es", "audio.wav", task="transcribe")

    assert result and isinstance(result, str)
    mock_processor.get_decoder_prompt_ids.assert_not_called()


@patch("infer.librosa.load", return_value=FAKE_AUDIO)
@patch("infer.WhisperForConditionalGeneration")
@patch("infer.WhisperProcessor")
def test_translate_task(mock_proc_cls, mock_model_cls, _load):
    mock_processor, mock_model = make_mocks()
    mock_proc_cls.from_pretrained.return_value = mock_processor
    mock_model_cls.from_pretrained.return_value = mock_model.return_value

    from infer import transcribe

    result = transcribe("checkpoints/es", "audio.wav", task="translate")

    assert result and isinstance(result, str)
    mock_processor.get_decoder_prompt_ids.assert_called_once_with(task="translate")


@patch("infer.librosa.load", return_value=FAKE_AUDIO)
@patch("infer.WhisperForConditionalGeneration")
@patch("infer.WhisperProcessor")
def test_language_with_transcribe_task(mock_proc_cls, mock_model_cls, _load):
    mock_processor, mock_model = make_mocks()
    mock_proc_cls.from_pretrained.return_value = mock_processor
    mock_model_cls.from_pretrained.return_value = mock_model.return_value

    from infer import transcribe

    result = transcribe("checkpoints/es", "audio.wav", language="spanish", task="transcribe")

    assert result and isinstance(result, str)
    mock_processor.get_decoder_prompt_ids.assert_called_once_with(
        language="spanish", task="transcribe"
    )


@patch("infer.librosa.load", return_value=FAKE_AUDIO)
@patch("infer.WhisperForConditionalGeneration")
@patch("infer.WhisperProcessor")
def test_language_with_translate_task(mock_proc_cls, mock_model_cls, _load):
    mock_processor, mock_model = make_mocks()
    mock_proc_cls.from_pretrained.return_value = mock_processor
    mock_model_cls.from_pretrained.return_value = mock_model.return_value

    from infer import transcribe

    result = transcribe("checkpoints/es", "audio.wav", language="spanish", task="translate")

    assert result and isinstance(result, str)
    mock_processor.get_decoder_prompt_ids.assert_called_once_with(
        language="spanish", task="translate"
    )
