# Project Memory

## Task 2 — Company Brain: deferred issues

Two items were scoped out of the Task 2 issue breakdown and deferred for later:

1. **Whisper large-v3 training support** — add `whisper-large-v3` as a model option in `1-train/train.py`. Not needed for core Company Brain features; the pre-trained model can be used directly for inference. Deferred because nothing in Task 2 depends on training large-v3.

2. **Benchmarking + MLflow** — `benchmark.py` (WER A/B, synthetic query recall, cross-language retrieval, end-to-end latency) + `mlflow_config.yaml`. PRD Goals 5, 6, 7, 8. User deferred this; write the issue when asked.
