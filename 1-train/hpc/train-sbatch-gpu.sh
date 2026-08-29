#!/bin/bash
# SLURM array job: Fine-tune openai/whisper-small on Google FLEURS across 5 languages on GPU.
#
# Languages (array indices 0-4):
#   0: en (English)
#   1: es (Spanish)
#   2: fr (French)
#   3: zh-CN (Mandarin)
#   4: ar (Arabic)
#
# Submit Examples:
#   sbatch train-sbatch-gpu.sh              # Submit all 5 languages in parallel
#   sbatch --array=0 train-sbatch-gpu.sh    # Submit English only (task 0)
#   sbatch --array=1 train-sbatch-gpu.sh    # Submit Spanish only (task 1)
#   sbatch --array=0,1 train-sbatch-gpu.sh  # Submit English and Spanish
#
# Monitor:
#   squeue -u $USER
#   tail -f logs/<jobid>_<arrayindex>.out
#   ssh $(squeue -u $USER -h -o "%N" | head -1) watch -n 1 rocm-smi
#

#SBATCH --job-name=whisper-finetune
#SBATCH --array=0-4                  # one task per language
#SBATCH --gres=gpu:1                 # 1 GPU per task
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --time=08:00:00
#SBATCH --output=logs/%A_%a.out      # logs/jobid_arrayindex.out
#SBATCH --error=logs/%A_%a.err
#SBATCH --account=project_465003209
#SBATCH --partition=small-g

# Language list — index must match --array range
LANGUAGES=("en" "es" "fr" "zh-CN" "ar")
LANG=${LANGUAGES[$SLURM_ARRAY_TASK_ID]}

echo "============================================"
echo "Job ID      : $SLURM_JOB_ID"
echo "Array index : $SLURM_ARRAY_TASK_ID"
echo "Language    : $LANG"
echo "Node        : $(hostname)"
echo "GPU         : $(rocm-smi --showproductname 2>/dev/null | grep 'Card Series' | head -1)"
echo "============================================"

# Path to the Singularity image (pull once with: singularity pull whisper-hpc.sif docker://ghcr.io/YOUR_ORG/whisper-hpc:latest)
#SIF=${SIF:-$HOME/whisper-hpc.sif}
SIF=/scratch/project_465003209/mcgowank/whisper-hpc.sif

# SLURM_SUBMIT_DIR is the directory sbatch was run from — go up two levels to project root
PROJECT_ROOT="$(cd "$SLURM_SUBMIT_DIR/../.." && pwd)"

# Shared HuggingFace dataset cache — avoids re-downloading FLEURS across all 5 jobs
#HF_CACHE=${HF_CACHE:-/scratch/$USER/hf_cache}
HF_CACHE=${HF_CACHE:-/scratch/project_465003209/mcgowank/hf_cache}
mkdir -p "$HF_CACHE" "$PROJECT_ROOT/logs" "$PROJECT_ROOT/checkpoints/$LANG"

# rocm/6.1 host drivers must be visible for --rocm to work; load if your cluster uses modules
# module load rocm/6.1
singularity exec \
    --rocm \
    --bind "$PROJECT_ROOT:/workspace" \
    --bind "$HF_CACHE:/hf_cache" \
    --env HF_HOME=/hf_cache \
    "$SIF" \
    bash -c "
        export LD_LIBRARY_PATH=/opt/rocm/lib:/opt/rocm/lib64:/usr/local/lib
        python /workspace/1-train/train.py \
            --language '$LANG' \
            --output_dir '/workspace/checkpoints/$LANG' \
            --epochs 3 \
            --batch_size 16 \
            --learning_rate 1e-5
    "

