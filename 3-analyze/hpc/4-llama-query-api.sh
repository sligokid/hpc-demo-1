curl -s -X POST http://$(cat /scratch/project_465003209/mcgowank/ollama.endpoint)/api/generate \
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
