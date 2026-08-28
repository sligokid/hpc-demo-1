#!/bin/bash
# Whisper training test on Linux - Spanish test
python ../train.py --language es --output_dir ./checkpoints/es --max_train_samples 200 --epochs 1 --batch_size 2
