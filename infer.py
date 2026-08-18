"""
Transcribe an audio file using a fine-tuned Whisper checkpoint.

Usage:
    python infer.py --model_dir checkpoints/es --audio path/to/audio.wav
    python infer.py --model_dir checkpoints/fr --audio path/to/audio.mp3 --language french
"""

import argparse
from typing import Optional
import torch
import librosa
from transformers import pipeline

SAMPLING_RATE = 16_000


def transcribe(model_dir: str, audio_path: str, language: Optional[str] = None, task: str = "transcribe") -> str:
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
    )

    result = pipe({"array": audio, "sampling_rate": SAMPLING_RATE}, generate_kwargs=generate_kwargs)
    return result["text"]


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
    args = parser.parse_args()

    print(f"Model : {args.model_dir}")
    print(f"Audio : {args.audio}")
    label = "Translation" if args.task == "translate" else "Transcription"
    verb = "Translating" if args.task == "translate" else "Transcribing"
    print(f"{verb}...")
    result = transcribe(args.model_dir, args.audio, args.language, args.task)
    print(f"\n{label}:\n{result}")


if __name__ == "__main__":
    main()
