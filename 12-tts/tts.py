"""
12-tts/tts.py — Teleprompter-to-Audio TTS stage.

Reads a {stem}.teleprompter.md, extracts Audio table fields only,
calls Ollama phonon via POST /v1/audio/speech for each text chunk,
and writes a single concatenated {stem}.teleprompter.wav.

Usage:
    python 12-tts/tts.py --input  results/en/myvideo.teleprompter.md \
                         --output results/en/myvideo \
                         --ollama-host localhost:11434 \
                         --voice Freya
"""

import argparse
import io
import pathlib
import re
import struct
import sys
import wave

import requests


CHUNK_LIMIT = 4096
DEFAULT_VOICE = "Freya"
DEFAULT_MODEL = "phonon"


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def extract_audio_text(md_text: str) -> str:
    """Extract spoken audio content from a teleprompter markdown file.

    Includes plain prose paragraphs. Excludes headings, VISUAL: cues,
    horizontal rules, bold metadata lines, checklist items, and the
    SME Review Checklist section.
    """
    lines = []
    for line in md_text.splitlines():
        stripped = line.strip()
        # Stop at SME Review Checklist — nothing after is audio
        if re.match(r'^#+ SME Review', stripped, re.IGNORECASE):
            break
        if not stripped:
            continue
        if stripped.startswith('#'):
            continue
        if stripped.startswith('VISUAL:'):
            continue
        if stripped == '---':
            continue
        if stripped.startswith('**'):
            continue
        if stripped.startswith('- ['):
            continue
        if stripped == '[PAUSE]':
            continue
        lines.append(stripped)
    return " ".join(lines)


# ---------------------------------------------------------------------------
# Cleaning
# ---------------------------------------------------------------------------

def clean_text(text: str) -> str:
    """Strip [PAUSE] markers and residual markdown formatting."""
    text = re.sub(r'\[PAUSE\]', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\*+', '', text)
    text = re.sub(r'`+', '', text)
    text = re.sub(r' {2,}', ' ', text)
    return text.strip()


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def chunk_text(text: str, limit: int = CHUNK_LIMIT) -> list:
    """Split text at sentence boundaries into chunks of at most `limit` chars."""
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    chunks = []
    current: list = []
    current_len = 0
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        add_len = len(sentence) + (1 if current else 0)
        if current and current_len + add_len > limit:
            chunks.append(" ".join(current))
            current = [sentence]
            current_len = len(sentence)
        else:
            current.append(sentence)
            current_len += add_len
    if current:
        chunks.append(" ".join(current))
    return chunks


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def _call_tts(text: str, ollama_host: str, voice: str, model: str = DEFAULT_MODEL) -> bytes:
    """POST to Ollama /v1/audio/speech and return raw WAV bytes."""
    url = f"http://{ollama_host}/v1/audio/speech"
    try:
        resp = requests.post(
            url,
            json={"model": model, "input": text, "voice": voice},
            timeout=300,
        )
    except requests.exceptions.ConnectionError:
        print(f"Error: could not connect to Ollama at {ollama_host}. Is it running?", file=sys.stderr)
        sys.exit(1)
    if not resp.ok:
        print(f"Error: Ollama TTS returned {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
        sys.exit(1)
    return resp.content


# ---------------------------------------------------------------------------
# WAV concatenation
# ---------------------------------------------------------------------------

def _concat_wavs(wav_buffers: list) -> bytes:
    """Concatenate a list of WAV byte strings into a single WAV.

    Reads frames in small increments to handle streaming WAV headers
    (where nframes is set to 0xFFFFFFFF), then builds the output header
    manually to avoid struct overflow in Python's wave writer.
    """
    all_pcm = []
    params = None

    for buf in wav_buffers:
        with wave.open(io.BytesIO(buf), 'r') as w:
            if params is None:
                params = w.getparams()
            while True:
                chunk = w.readframes(4096)
                if not chunk:
                    break
                all_pcm.append(chunk)

    pcm_data = b''.join(all_pcm)
    data_size = len(pcm_data)
    byte_rate = params.nchannels * params.framerate * params.sampwidth
    block_align = params.nchannels * params.sampwidth
    bits_per_sample = params.sampwidth * 8

    header = struct.pack(
        '<4sL4s4sLHHLLHH4sL',
        b'RIFF', 36 + data_size,
        b'WAVE',
        b'fmt ', 16,
        1,  # PCM
        params.nchannels,
        params.framerate,
        byte_rate,
        block_align,
        bits_per_sample,
        b'data', data_size,
    )
    return header + pcm_data


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate(
    input_path: pathlib.Path,
    output_stem: pathlib.Path,
    ollama_host: str = "localhost:11434",
    voice: str = DEFAULT_VOICE,
    model: str = DEFAULT_MODEL,
) -> pathlib.Path:
    """Generate a WAV file from a teleprompter markdown file. Returns wav_path."""
    wav_path = output_stem.parent / (output_stem.name + ".teleprompter.wav")

    if wav_path.exists():
        return wav_path

    md_text = pathlib.Path(input_path).read_text()
    raw_text = extract_audio_text(md_text)
    clean = clean_text(raw_text)

    if not clean:
        print("Warning: no audio content found in input.", file=sys.stderr)
        return wav_path

    chunks = chunk_text(clean)
    wav_buffers = []
    for i, chunk in enumerate(chunks, 1):
        print(f"  chunk {i}/{len(chunks)} ({len(chunk)} chars)")
        wav_buffers.append(_call_tts(chunk, ollama_host, voice, model))

    wav_path.write_bytes(_concat_wavs(wav_buffers))
    return wav_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Convert teleprompter markdown to WAV audio.")
    parser.add_argument("--input",       required=True, help="Path to .teleprompter.md file")
    parser.add_argument("--output",      required=True, help="Output stem (e.g. results/en/myvideo)")
    parser.add_argument("--ollama-host", default="localhost:11434", help="Ollama host:port")
    parser.add_argument("--voice",       default=DEFAULT_VOICE,     help="Phonon voice name")
    parser.add_argument("--model",       default=DEFAULT_MODEL,     help="Ollama TTS model name")
    args = parser.parse_args()

    input_path  = pathlib.Path(args.input)
    output_stem = pathlib.Path(args.output)
    output_stem.parent.mkdir(parents=True, exist_ok=True)

    wav_path = generate(
        input_path=input_path,
        output_stem=output_stem,
        ollama_host=args.ollama_host,
        voice=args.voice,
        model=args.model,
    )
    print(f"WAV written -> {wav_path}")


if __name__ == "__main__":
    main()
