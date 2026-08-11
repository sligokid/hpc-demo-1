"""
Fine-tune openai/whisper-small on Mozilla Common Voice for a single language.
Intended to be launched as one job in a SLURM array (one language per job).

Usage:
    python train.py --language es --output_dir ./checkpoints/es
"""

import argparse
import os

import evaluate
import torch
from dataclasses import dataclass
from typing import Any, Dict, List, Union

from datasets import load_dataset, Audio
from transformers import (
    WhisperProcessor,
    WhisperForConditionalGeneration,
    Seq2SeqTrainer,
    Seq2SeqTrainingArguments,
)

LANGUAGE_CODES = {
    "en": "english",
    "es": "spanish",
    "fr": "french",
    "zh-CN": "chinese",
    "ar": "arabic",
}

COMMON_VOICE_SPLITS = {
    "en": "en",
    "es": "es",
    "fr": "fr",
    "zh-CN": "zh-CN",
    "ar": "ar",
}

MODEL_ID = "openai/whisper-small"
SAMPLING_RATE = 16_000


def load_common_voice(language_code: str):
    split = COMMON_VOICE_SPLITS[language_code]
    dataset = load_dataset(
        "mozilla-foundation/common_voice_11_0",
        split,
        split={"train": "train", "validation": "validation"},
        trust_remote_code=True,
    )
    # Keep only the columns we need
    columns_to_remove = [
        c for c in dataset["train"].column_names
        if c not in ("audio", "sentence")
    ]
    dataset = dataset.remove_columns(columns_to_remove)
    dataset = dataset.cast_column("audio", Audio(sampling_rate=SAMPLING_RATE))
    return dataset


def prepare_dataset(batch, processor, language_name):
    audio = batch["audio"]
    batch["input_features"] = processor.feature_extractor(
        audio["array"], sampling_rate=audio["sampling_rate"]
    ).input_features[0]

    batch["labels"] = processor.tokenizer(batch["sentence"]).input_ids
    return batch


@dataclass
class DataCollatorSpeechSeq2SeqWithPadding:
    processor: Any

    def __call__(self, features: List[Dict[str, Union[List[int], torch.Tensor]]]):
        input_features = [
            {"input_features": f["input_features"]} for f in features
        ]
        batch = self.processor.feature_extractor.pad(
            input_features, return_tensors="pt"
        )

        label_features = [{"input_ids": f["labels"]} for f in features]
        labels_batch = self.processor.tokenizer.pad(
            label_features, return_tensors="pt"
        )
        labels = labels_batch["input_ids"].masked_fill(
            labels_batch.attention_mask.ne(1), -100
        )
        # Strip BOS token if present
        if (labels[:, 0] == self.processor.tokenizer.bos_token_id).all():
            labels = labels[:, 1:]

        batch["labels"] = labels
        return batch


def compute_metrics_fn(pred, processor):
    wer_metric = evaluate.load("wer")
    pred_ids = pred.predictions
    label_ids = pred.label_ids
    label_ids[label_ids == -100] = processor.tokenizer.pad_token_id

    pred_str = processor.tokenizer.batch_decode(pred_ids, skip_special_tokens=True)
    label_str = processor.tokenizer.batch_decode(label_ids, skip_special_tokens=True)

    wer = wer_metric.compute(predictions=pred_str, references=label_str)
    return {"wer": round(wer, 4)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--language", required=True, choices=list(LANGUAGE_CODES.keys()))
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--learning_rate", type=float, default=1e-5)
    parser.add_argument("--max_train_samples", type=int, default=None,
                        help="Cap training set size (useful for quick smoke tests)")
    args = parser.parse_args()

    language_name = LANGUAGE_CODES[args.language]
    os.makedirs(args.output_dir, exist_ok=True)

    print(f"[{args.language}] Loading processor and model...")
    processor = WhisperProcessor.from_pretrained(
        MODEL_ID, language=language_name, task="transcribe"
    )
    model = WhisperForConditionalGeneration.from_pretrained(MODEL_ID)
    model.generation_config.language = language_name
    model.generation_config.task = "transcribe"
    model.generation_config.forced_decoder_ids = None

    print(f"[{args.language}] Loading Common Voice dataset...")
    dataset = load_common_voice(args.language)

    if args.max_train_samples:
        dataset["train"] = dataset["train"].select(range(args.max_train_samples))

    print(f"[{args.language}] Preprocessing...")
    dataset = dataset.map(
        lambda b: prepare_dataset(b, processor, language_name),
        remove_columns=dataset["train"].column_names,
        num_proc=4,
    )

    data_collator = DataCollatorSpeechSeq2SeqWithPadding(processor=processor)

    training_args = Seq2SeqTrainingArguments(
        output_dir=args.output_dir,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=8,
        gradient_accumulation_steps=2,
        learning_rate=args.learning_rate,
        warmup_steps=100,
        num_train_epochs=args.epochs,
        gradient_checkpointing=True,
        fp16=torch.cuda.is_available(),
        evaluation_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="wer",
        greater_is_better=False,
        predict_with_generate=True,
        generation_max_length=225,
        logging_steps=25,
        report_to="none",
        push_to_hub=False,
    )

    trainer = Seq2SeqTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset["train"],
        eval_dataset=dataset["validation"],
        tokenizer=processor.feature_extractor,
        data_collator=data_collator,
        compute_metrics=lambda pred: compute_metrics_fn(pred, processor),
    )

    print(f"[{args.language}] Starting training...")
    trainer.train()

    print(f"[{args.language}] Saving final model to {args.output_dir}...")
    trainer.save_model(args.output_dir)
    processor.save_pretrained(args.output_dir)
    print(f"[{args.language}] Done.")


if __name__ == "__main__":
    main()
