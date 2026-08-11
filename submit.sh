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

# Load modules — adjust to your cluster's module system
module load python/3.11
module load rocm/6.1

# Activate virtualenv (create once with: python -m venv venv && pip install -r requirements.txt)
source venv/bin/activate

mkdir -p logs checkpoints/$LANG

python train.py \
    --language "$LANG" \
    --output_dir "checkpoints/$LANG" \
    --epochs 3 \
    --batch_size 16 \
    --learning_rate 1e-5
