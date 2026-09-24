mkdir -p /tmp/$USER
export SINGULARITY_TMPDIR=/tmp/$USER
export SINGULARITY_CACHEDIR=/tmp/$USER

singularity pull ../whisper-hpc.sif docker://sligokid/whisper-hpc:latest
singularity pull ../whisper-sync.sif docker://sligokid/whisper-sync:latest
singularity pull ../ollama.sif docker://ollama/ollama:rocm
singularity pull ../qdrant.sif docker://qdrant/qdrant:latest
singularity pull ../embeddings-api.sif docker://sligokid/embeddings-api:latest
