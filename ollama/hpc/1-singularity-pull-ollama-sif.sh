SCRATCH=/scratch/project_465003209/mcgowank
OLLAMA_SIF=${OLLAMA_SIF:-$SCRATCH/ollama.sif}

singularity pull $OLLAMA_SIF docker://ollama/ollama:rocm
