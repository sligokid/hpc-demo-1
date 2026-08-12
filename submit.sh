#!/bin/bash
#SBATCH --job-name=whisper-finetune
#SBATCH --array=0-4                  # one task per language
#SBATCH --gres=gpu:1                 # 1 GPU per task
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=08:00:00
#SBATCH --output=logs/%A_%a.out      # logs/jobid_arrayindex.out
#SBATCH --error=logs/%A_%a.err

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
SIF=${SIF:-$HOME/whisper-hpc.sif}

# Shared HuggingFace dataset cache — avoids re-downloading FLEURS across all 5 jobs
HF_CACHE=${HF_CACHE:-/scratch/$USER/hf_cache}
mkdir -p "$HF_CACHE" logs "checkpoints/$LANG"

# rocm/6.1 host drivers must be visible for --rocm to work; load if your cluster uses modules
# module load rocm/6.1

singularity exec \
    --rocm \
    --bind "$PWD:/workspace" \
    --bind "$HF_CACHE:/hf_cache" \
    --env HF_HOME=/hf_cache \
    "$SIF" \
    python /workspace/train.py \
        --language "$LANG" \
        --output_dir "/workspace/checkpoints/$LANG" \
        --epochs 3 \
        --batch_size 16 \
        --learning_rate 1e-5
