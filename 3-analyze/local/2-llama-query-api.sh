#!/bin/bash

curl -s -X POST http://localhost:11434/api/generate  -H 'Content-Type: application/json'  -d '{
"model": "llama3.1:8b",
      "prompt": "What is the capital of France?",
      "stream": false,
      "options": {
        "temperature": 0.7,
        "num_predict": 100
      }
}' | jq '.response'
