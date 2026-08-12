FROM rocm/pytorch:rocm6.1.3_ubuntu22.04_py3.10_pytorch_release-2.1.2

WORKDIR /workspace

# System deps required by librosa and soundfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# torch is already installed in the base image (ROCm build).
# Exclude it here to avoid pip overwriting it with a CPU wheel from PyPI.
RUN grep -v "^torch" requirements.txt | pip install --no-cache-dir -r /dev/stdin

# Checkpoints, logs, and HF cache are supplied via bind mounts at runtime.
# No CMD — invoke explicitly via: singularity exec ... python /workspace/train.py
