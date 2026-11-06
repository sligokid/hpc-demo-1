import io
import pathlib
import wave

import pytest

import tts


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_wav(num_frames: int = 100) -> bytes:
    """Return a minimal valid 16-bit mono 24kHz WAV of silence."""
    buf = io.BytesIO()
    with wave.open(buf, 'w') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(b'\x00\x00' * num_frames)
    return buf.getvalue()


TELEPROMPTER_MD = """\
# My Procedure — Teleprompter Video Script

**SOP Title:** My Procedure
**Estimated Runtime:** ~30 sec

---

## SECTION 1 — Hook & Intro

VISUAL: Title card / Presenter on camera

---

Hi, I'm [Presenter Name].

Welcome to this procedure.

[PAUSE]

Let's get started.

---

## SECTION 2 — Step-by-Step Walkthrough

---

### STEP ONE — Open the Application

VISUAL: Screen recording: open the app

---

Open the application and log in.

[PAUSE]

Navigate to the Settings panel.

---

### STEP TWO — Upload Your File

VISUAL: Drag-and-drop interface

---

Upload your source file using drag and drop.

[PAUSE]

Click Generate to continue.

---

## SECTION 4 — Outro & Call to Action

VISUAL: Presenter back on camera

---

You have completed the procedure successfully.

---

# SME Review Checklist

- [ ] Presenter name filled in
- [ ] Sign-off: Reviewed by: _______
"""


@pytest.fixture
def mock_tts(mocker):
    mock = mocker.patch("requests.post")
    mock.return_value.ok = True
    mock.return_value.content = _make_wav(200)
    return mock


# ---------------------------------------------------------------------------
# extract_audio_text
# ---------------------------------------------------------------------------

def test_extract_returns_audio_content():
    text = tts.extract_audio_text(TELEPROMPTER_MD)
    assert "Welcome to this procedure" in text
    assert "Open the application and log in" in text
    assert "Upload your source file" in text
    assert "You have completed the procedure" in text


def test_extract_excludes_visual_cues():
    text = tts.extract_audio_text(TELEPROMPTER_MD)
    assert "Screen recording" not in text
    assert "Drag-and-drop interface" not in text


def test_extract_excludes_headings():
    text = tts.extract_audio_text(TELEPROMPTER_MD)
    assert "SECTION 1" not in text
    assert "STEP ONE" not in text


def test_extract_excludes_checklist():
    text = tts.extract_audio_text(TELEPROMPTER_MD)
    assert "SME Review" not in text
    assert "Presenter name filled in" not in text


def test_extract_excludes_metadata():
    text = tts.extract_audio_text(TELEPROMPTER_MD)
    assert "SOP Title" not in text
    assert "Estimated Runtime" not in text


def test_extract_empty_when_no_prose():
    md = "# Heading\n\nVISUAL: Something\n\n---\n"
    assert tts.extract_audio_text(md) == ""


# ---------------------------------------------------------------------------
# clean_text
# ---------------------------------------------------------------------------

def test_clean_strips_pause_markers():
    result = tts.clean_text("Hello. [PAUSE] World.")
    assert "[PAUSE]" not in result
    assert "Hello" in result
    assert "World" in result


def test_clean_strips_bold():
    result = tts.clean_text("Click **Generate** to continue.")
    assert "**" not in result
    assert "Generate" in result


def test_clean_strips_backticks():
    result = tts.clean_text("Run `python tts.py` now.")
    assert "`" not in result
    assert "python tts.py" in result


def test_clean_collapses_spaces():
    result = tts.clean_text("Hello   world.")
    assert "  " not in result


# ---------------------------------------------------------------------------
# chunk_text
# ---------------------------------------------------------------------------

def test_chunk_single_short_text():
    chunks = tts.chunk_text("Hello world.")
    assert chunks == ["Hello world."]


def test_chunk_splits_at_sentence_boundary():
    # Two sentences of 2100 chars each: combined length 4201 > 4096, so must split
    long_sentence = "A" * 2099 + "."
    text = long_sentence + " " + long_sentence
    chunks = tts.chunk_text(text, limit=4096)
    assert len(chunks) == 2
    assert all(len(c) <= 4096 for c in chunks)


def test_chunk_no_chunk_exceeds_limit():
    sentences = ["Word " * 50 + "." for _ in range(20)]
    text = " ".join(sentences)
    chunks = tts.chunk_text(text, limit=4096)
    for chunk in chunks:
        assert len(chunk) <= 4096


def test_chunk_preserves_all_content():
    text = "First sentence. Second sentence. Third sentence."
    chunks = tts.chunk_text(text)
    rejoined = " ".join(chunks)
    assert "First sentence" in rejoined
    assert "Second sentence" in rejoined
    assert "Third sentence" in rejoined


# ---------------------------------------------------------------------------
# _concat_wavs
# ---------------------------------------------------------------------------

def test_concat_produces_valid_wav():
    bufs = [_make_wav(100), _make_wav(200)]
    result = tts._concat_wavs(bufs)
    with wave.open(io.BytesIO(result), 'r') as w:
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.getframerate() == 24000
        assert w.getnframes() == 300


def test_concat_single_buffer():
    buf = _make_wav(50)
    result = tts._concat_wavs([buf])
    with wave.open(io.BytesIO(result), 'r') as w:
        assert w.getnframes() == 50


# ---------------------------------------------------------------------------
# generate (integration with mocked requests.post)
# ---------------------------------------------------------------------------

def test_generate_writes_wav_file(tmp_path, mock_tts):
    md_file = tmp_path / "demo.teleprompter.md"
    md_file.write_text(TELEPROMPTER_MD)
    stem = tmp_path / "demo"

    wav_path = tts.generate(md_file, stem)

    assert wav_path.exists()
    assert wav_path.name == "demo.teleprompter.wav"


def test_generate_output_is_valid_wav(tmp_path, mock_tts):
    md_file = tmp_path / "demo.teleprompter.md"
    md_file.write_text(TELEPROMPTER_MD)

    tts.generate(md_file, tmp_path / "demo")

    wav_path = tmp_path / "demo.teleprompter.wav"
    with wave.open(str(wav_path), 'r') as w:
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.getframerate() == 24000


def test_generate_calls_api_once_per_chunk(tmp_path, mock_tts):
    md_file = tmp_path / "demo.teleprompter.md"
    md_file.write_text(TELEPROMPTER_MD)

    tts.generate(md_file, tmp_path / "demo")

    assert mock_tts.call_count >= 1


def test_generate_idempotent(tmp_path, mock_tts):
    md_file = tmp_path / "demo.teleprompter.md"
    md_file.write_text(TELEPROMPTER_MD)
    wav_path = tmp_path / "demo.teleprompter.wav"
    wav_path.write_bytes(_make_wav(10))

    tts.generate(md_file, tmp_path / "demo")

    mock_tts.assert_not_called()


def test_generate_no_audio_fields_writes_nothing(tmp_path, mock_tts):
    md_file = tmp_path / "empty.teleprompter.md"
    md_file.write_text("# Heading Only\n\nVISUAL: Something\n\n---\n")

    tts.generate(md_file, tmp_path / "empty")

    mock_tts.assert_not_called()
    assert not (tmp_path / "empty.teleprompter.wav").exists()
