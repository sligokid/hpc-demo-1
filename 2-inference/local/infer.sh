#!/bin/bash
# Infer on a single GPU using the fine-tuned EN checkpoint
python ../infer.py --model_dir ../../checkpoints/en --audio ../audio/sligo-triathlon-club-inviting-women-to-try-a-tri.mp3