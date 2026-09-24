#!/bin/bash
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
[ -f "$PROJECT_ROOT/.env" ] && source "$PROJECT_ROOT/.env"
SCRATCH=${HPC_SCRATCH:?".env must define HPC_SCRATCH"}

curl -s -X POST http://$(cat "$SCRATCH/ollama.endpoint")/api/generate \
    -H 'Content-Type: application/json' \
    -d '{
      "model": "llama3",
      "prompt": "What is the capital of France?",
      "stream": false,
      "options": {
        "temperature": 0.7,
        "num_predict": 100
      }
    }' | jq '.response'
