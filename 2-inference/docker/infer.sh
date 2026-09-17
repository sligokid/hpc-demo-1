#!/bin/bash
# Infer on a single CPU using the fine-tuned EN checkpoint in a Docker container (NO GPU in docker engine)
docker compose run dev python 2-inference/infer.py --model_dir checkpoints/en --audio 2-inference/audio/sligo-triathlon-club-inviting-women-to-try-a-tri.mp3 --segments