"""
Transcribe an audio file using a fine-tuned Whisper checkpoint.

Usage:
    python infer.py --model_dir checkpoints/es --audio path/to/audio.wav
    python infer.py --model_dir checkpoints/fr --audio path/to/audio.mp3 --language french
    python infer.py --model_dir checkpoints/es --audio audio.mp3 --segments
"""

import argparse
import json
import os
from typing import Optional
import torch
import librosa
from transformers import pipeline

SAMPLING_RATE = 16_000


def _run_pipeline(model_dir: str, audio_path: str, language: Optional[str] = None,
                  task: str = "transcribe", return_timestamps: bool = False):
    if torch.cuda.is_available():
        device = 0  # pipeline expects int device index for CUDA
    elif torch.backends.mps.is_available():
        device = "mps"
    else:
        device = -1  # CPU

    generate_kwargs = {"task": task}
    if language:
        generate_kwargs["language"] = language

    audio, _ = librosa.load(audio_path, sr=SAMPLING_RATE, mono=True)

    pipe = pipeline(
        "automatic-speech-recognition",
        model=model_dir,
        device=device,
        chunk_length_s=30,
        stride_length_s=5,
        return_timestamps=return_timestamps,
    )

    return pipe({"array": audio, "sampling_rate": SAMPLING_RATE}, generate_kwargs=generate_kwargs)


def transcribe(model_dir: str, audio_path: str, language: Optional[str] = None, task: str = "transcribe") -> str:
    return _run_pipeline(model_dir, audio_path, language, task)["text"]


def transcribe_with_segments(model_dir: str, audio_path: str, language: Optional[str] = None, task: str = "transcribe"):
    """Return (text, segments) where segments is [{start, end, text}, ...]."""
    result = _run_pipeline(model_dir, audio_path, language, task, return_timestamps=True)
    segments = [
        {"start": float(c["timestamp"][0]), "end": float(c["timestamp"][1]), "text": c["text"]}
        for c in result["chunks"]
        if c["timestamp"][0] is not None and c["timestamp"][1] is not None
    ]
    return result["text"], segments


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_dir", required=True,
                        help="Path to fine-tuned checkpoint directory")
    parser.add_argument("--audio", required=True,
                        help="Path to audio file (.wav, .mp3, etc.)")
    parser.add_argument("--language", default=None,
                        help="Force decode language (e.g. 'spanish'). "
                             "Defaults to model's trained language.")
    parser.add_argument("--task", default="transcribe",
                        choices=["transcribe", "translate"],
                        help="Task to perform: 'transcribe' (default) or 'translate' (outputs English).")
    parser.add_argument("--segments", action="store_true",
                        help="Emit transcript.txt and segments.json alongside the audio file.")
    args = parser.parse_args()

    print(f"Model : {args.model_dir}")
    print(f"Audio : {args.audio}")
    label = "Translation" if args.task == "translate" else "Transcription"
    verb = "Translating" if args.task == "translate" else "Transcribing"
    print(f"{verb}...")

    if args.segments:
        text, segments = transcribe_with_segments(args.model_dir, args.audio, args.language, args.task)
        out_dir = os.path.dirname(os.path.abspath(args.audio))
        transcript_path = os.path.join(out_dir, "transcript.txt")
        segments_path = os.path.join(out_dir, "segments.json")
        with open(transcript_path, "w") as f:
            f.write(text)
        with open(segments_path, "w") as f:
            json.dump(segments, f, indent=2)
        print(f"transcript.txt → {transcript_path}")
        print(f"segments.json  → {segments_path}")
    else:
        text = transcribe(args.model_dir, args.audio, args.language, args.task)

    print(f"\n{label}:\n{text}")


if __name__ == "__main__":
    main()
