"""
Transcribe an audio file using a fine-tuned Whisper checkpoint.

Usage:
    python infer.py --model_dir checkpoints/es --audio path/to/audio.wav
    python infer.py --model_dir checkpoints/fr --audio path/to/audio.mp3 --language french
"""

import argparse
from typing import Optional
import librosa
import torch
from transformers import pipeline

SAMPLING_RATE = 16_000


def transcribe(model_dir: str, audio_path: str, language: Optional[str] = None) -> str:
    if torch.cuda.is_available():
        device = "cuda"
    elif torch.backends.mps.is_available():
        device = "mps"
    else:
        device = "cpu"

    generate_kwargs = {}
    if language:
        generate_kwargs["language"] = language
        generate_kwargs["task"] = "transcribe"

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
    args = parser.parse_args()

    print(f"Model : {args.model_dir}")
    print(f"Audio : {args.audio}")
    print("Transcribing...")
    result = transcribe(args.model_dir, args.audio, args.language)
    print(f"\nTranscription:\n{result}")


if __name__ == "__main__":
    main()
