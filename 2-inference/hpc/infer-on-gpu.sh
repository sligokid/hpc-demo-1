#!/bin/bash
# Interactive srun job: Run Whisper transcription on GPU.
#
# Usage:
#   ./infer-on-gpu.sh
#

PROJECT_ROOT="$(cd "$PWD/../.." && pwd)"

# Load site config (.env — never committed)
[ -f "$PROJECT_ROOT/.env" ] && source "$PROJECT_ROOT/.env"
SCRATCH=${HPC_SCRATCH:?".env must define HPC_SCRATCH"}
SIF=$SCRATCH/whisper-hpc.sif

srun --account "${HPC_ACCOUNT:?}" --partition=small-g --time=04:00:00 --ntasks=1 --cpus-per-task=1 --nodes=1 --mem=128GB --gres=gpu:1 singularity exec --rocm --bind "$PROJECT_ROOT:/workspace" "$SIF" bash -c "
export LD_LIBRARY_PATH=/opt/rocm/lib:/opt/rocm/lib64:/usr/local/lib
export MIOPEN_DISABLE_CACHE=1
python /workspace/2-inference/infer-full.py --model_dir /workspace/checkpoints/en/ --audio /workspace/2-inference/audio/sligo-triathlon-club-inviting-women-to-try-a-tri.mp3
#"
