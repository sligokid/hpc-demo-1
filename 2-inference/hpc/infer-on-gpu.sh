#!/bin/bash
# Interactive srun job: Run Whisper transcription on GPU.
#
# Usage:
#   ./infer-on-gpu.sh
#

SIF=/scratch/project_465003209/mcgowank/whisper-hpc.sif
PROJECT_ROOT="$(cd "$PWD/../.." && pwd)"

#srun --account project_465003209 --partition=small-g --time=04:00:00 --ntasks=1 --cpus-per-task=1 --nodes=1 --mem=128GB --gres=gpu:1 singularity exec --rocm --bind "$PROJECT_ROOT:/workspace" "$SIF" bash -c "
#export LD_LIBRARY_PATH=/opt/rocm/lib:/opt/rocm/lib64:/usr/local/lib
#python /workspace/2-inference/infer.py --model_dir /workspace/checkpoints/en/ --audio /workspace/2-inference/audio/sligo-triathlon-club-inviting-women-to-try-a-tri.mp3
#"

srun --account project_465003209 --partition=small-g --time=04:00:00 --ntasks=1 --cpus-per-task=1 --nodes=1 --mem=128GB --gres=gpu:1 singularity exec --rocm --bind "$PROJECT_ROOT:/workspace" "$SIF" bash -c "
export LD_LIBRARY_PATH=/opt/rocm/lib:/opt/rocm/lib64:/usr/local/lib
export MIOPEN_DISABLE_CACHE=1
python /workspace/2-inference/infer-full.py --model_dir /workspace/checkpoints/en/ --audio /workspace/2-inference/audio/sligo-triathlon-club-inviting-women-to-try-a-tri.mp3
#"
