#!/bin/bash
# Infer and translate Spanish audio on a single GPU using the fine-tuned ES checkpoint

python ../infer.py --model_dir ../../checkpoints/es --audio ../audio/spanish-telephone-phrases.mp3 --task translate