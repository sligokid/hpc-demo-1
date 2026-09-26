#!/usr/bin/env bash
# Run the semantic search pipeline on a single query.
# Prerequisites: virtualenv active, Qdrant running.
# Run from the project root or this directory.
set -euo pipefail

cd "$(dirname "$0")/../.."

python 8-search/search.py --query "${1:-how can i find out more about the club}"
