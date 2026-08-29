#!/bin/bash
# Interactive srun job: Run Whisper transcription on CPU.
#
# Usage:
#   ./infer-on-cpu.sh
#

SIF=/scratch/project_465003209/mcgowank/hpc-demo-1/whisper-hpc.sif

#srun --account project_465003209 --partition=small-g --time=04:00:00 --ntasks=1 --cpus-per-task=1 --nodes=1 --mem=128GB singularity exec --bind "$PWD:/workspace" "$SIF" python /workspace/2-inference/infer.py --model_dir /workspace/checkpoints/en/ --audio /workspace/2-inference/audio/sligo-triathlon-club-inviting-women-to-try-a-tri.mp3
srun --account project_465003209 --partition=small-g --time=04:00:00 --ntasks=1 --cpus-per-task=1 --nodes=1 --mem=128GB singularity exec --bind "$PWD:/workspace" "$SIF" python /workspace/2-inference/infer-full.py --model_dir /workspace/checkpoints/en/ --audio /workspace/2-inference/audio/sligo-triathlon-club-inviting-women-to-try-a-tri.mp3
