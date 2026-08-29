#!/bin/bash
# Interactive srun job: Run Whisper Spanish audio to English translation on GPU.
#
# Usage:
#   ./infer-translate-on-gpu.sh
#

#srun --account project_465003209 --partition=small-g --time=04:00:00 --ntasks=1 --cpus-per-task=1 --nodes=1 --mem=128GB --gres=gpu:1 singularity exec --rocm --bind "$PWD:/workspace" whisper-hpc.sif bash -c "
#export LD_LIBRARY_PATH=/opt/rocm/lib:/opt/rocm/lib64:/usr/local/lib
#python /workspace/2-inference/infer.py --model_dir /workspace/checkpoints/en/ --audio /workspace/sligo-triathlon-club-inviting-women-to-try-a-tri.mp3
#"

srun --account project_465003209 --partition=small-g --time=04:00:00 --ntasks=1 --cpus-per-task=1 --nodes=1 --mem=128GB --gres=gpu:1 singularity exec --rocm --bind "$PWD:/workspace" whisper-hpc.sif bash -c "
export LD_LIBRARY_PATH=/opt/rocm/lib:/opt/rocm/lib64:/usr/local/lib
export MIOPEN_DISABLE_CACHE=1
python /workspace/2-inference/infer-full.py --model_dir /workspace/checkpoints/es/ --audio /workspace/spanish-telephone-phrases.mp3 --task translate
#"
