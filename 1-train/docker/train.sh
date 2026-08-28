#!/bin/bash
# Whisper training test on Docker Desktop - Spanish test
docker compose run dev python 1-train/train.py --language es --output_dir ./checkpoints/es --max_train_samples 200 --epochs 1