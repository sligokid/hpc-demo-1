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
from transformers import WhisperProcessor, WhisperForConditionalGeneration

SAMPLING_RATE = 16_000


def transcribe(model_dir: str, audio_path: str, language: Optional[str] = None) -> str:
    if torch.cuda.is_available():
        device = "cuda"
    elif torch.backends.mps.is_available():
        device = "mps"
    else:
        device = "cpu"

    processor = WhisperProcessor.from_pretrained(model_dir)
    model = WhisperForConditionalGeneration.from_pretrained(model_dir).to(device)
    model.eval()

    audio, _ = librosa.load(audio_path, sr=SAMPLING_RATE, mono=True)
    inputs = processor(audio, sampling_rate=SAMPLING_RATE, return_tensors="pt")
    input_features = inputs.input_features.to(device)

    forced_decoder_ids = None
    if language:
        forced_decoder_ids = processor.get_decoder_prompt_ids(
            language=language, task="transcribe"
        )

    with torch.no_grad():
        predicted_ids = model.generate(
            input_features,
            forced_decoder_ids=forced_decoder_ids,
        )

    return processor.batch_decode(predicted_ids, skip_special_tokens=True)[0]


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
