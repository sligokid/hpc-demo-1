# SLICK+ HPC Demo — Multilingual Whisper Fine-Tuning for ASR

Fine-tunes `openai/whisper-small` on [Google FLEURS](https://huggingface.co/datasets/google/fleurs) across five languages simultaneously using a SLURM job array on HPC GPU infrastructure. Demonstrates how multilingual speech model training that would take weeks on standard infrastructure can be reduced to days.

## Languages

| Code | Language | FLEURS locale |
|------|----------|---------------|
| `en` | English | `en_us` |
| `es` | Spanish | `es_419` |
| `fr` | French | `fr_fr` |
| `zh-CN` | Mandarin | `cmn_hans_cn` |
| `ar` | Arabic | `ar_eg` |

## Setup

### Mac (Apple Silicon) — local dev

Run directly in a virtualenv. PyTorch's MPS backend is used automatically; Docker cannot access it.

```bash
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
```

## Training <a name="training"></a>
Checkpoints are saved per epoch to `checkpoints/<lang>/`. The best checkpoint (lowest WER) is restored automatically at the end of training.

### Smoke test — single language, small sample — local dev

GPU enabled if present but not required

```bash
python train.py --language es --output_dir ./checkpoints/es --max_train_samples 200 --epochs 1 --batch_size 2
```

### Linux / CI — CPU-only Docker (GPU not supported on Mac)

```bash
docker compose run dev python train.py --language es --output_dir ./checkpoints/es --max_train_samples 200 --epochs 1
```

## Build via Docker <a name="build"></a>
**To build and push a new image** (run locally with Docker installed):

```bash
docker build -t sligokid/hpc-demo-1:latest .
docker push sligokid/hpc-demo-1:latest
```
**To build update and push a new image with amd64 support** edit `requirements.txt` or the `Dockerfile`, then rebuild and push:

```bash
docker buildx build --platform linux/amd64 -t sligokid/whisper-hpc:latest --push .
```

### HPC — Singularity conversion from Docker image (AMD/ROCm)

Pull the docker image once on the login node 

```bash
singularity pull ~/whisper-hpc.sif docker://sligokid/hpc-demo-1:latest
```
#### Set cache directories when using Docker containers

When pulling or building from Docker containers using singularity, the conversion can be quite heavy. Speed up the conversion and avoid leaving behind temporary files by using the in-memory filesystem on /tmp as the Singularity cache directory, 

i.e. On the worker node
```bash
$ mkdir -p /tmp/$USER
$ export SINGULARITY_TMPDIR=/tmp/$USER
$ export SINGULARITY_CACHEDIR=/tmp/$USER
singularity pull whisper-hpc.sif docker://sligokid/whisper-hpc:latest
```

**Full HPC run — all 5 languages in parallel:**
```bash
mkdir -p logs
sbatch submit.sh
```

Each language runs as an independent SLURM job (one GPU each). Monitor progress:

```bash
squeue -u $USER
tail -f logs/<jobid>_<arrayindex>.out
```


## Inference
Audio of any length is supported — the pipeline chunks into overlapping 30-second windows automatically.
```bash
python infer.py --model_dir checkpoints/es --audio path/to/audio.wav
python infer.py --model_dir checkpoints/fr --audio path/to/audio.mp3 --language french
```

### Translation mode

Pass `--task translate` to produce an English transcript from non-English audio without retraining:

```bash
python infer.py --model_dir checkpoints/es --audio path/to/audio.wav --task translate
```

**Constraints:**
- Translation always outputs **English**, regardless of source language — Whisper's translate task is English-output only.
- The five fine-tuned checkpoints were trained with `task="transcribe"`. Translation uses Whisper's pretrained translation head, not fine-tuned translation weights. Quality will vary by language and is generally weaker than transcription.
- `--language` continues to work alongside `--task translate` to force the source language when needed.

**Future extension:** to improve translation quality, `train.py` can be fine-tuned in translation mode by changing `task="transcribe"` to `task="translate"` and providing paired audio + English reference translations (FLEURS includes these). A separate output directory (e.g. `checkpoints/es-translate`) would be needed to avoid overwriting transcription checkpoints.

### HPC — Singularity (AMD/ROCm)
```bash
./infer-on-gpu.sh
```
### Example
```srun: job 21098926 queued and waiting for resources
srun: job 21098926 has been allocated resources
/opt/conda/envs/py_3.10/lib/python3.10/site-packages/transformers/models/whisper/generation_whisper.py:509: FutureWarning: The input name `inputs` is deprecated. Please make sure to use `input_features` instead.
  warnings.warn(
You have passed task=transcribe, but also have set `forced_decoder_ids` to [[1, 50259], [2, 50359], [3, 50363]] which creates a conflict. `forced_decoder_ids` will be ignored in favor of task=transcribe.
The attention mask is not set and cannot be inferred from input because pad token is same as eos token. As a consequence, you may observe unexpected behavior. Please pass your input's `attention_mask` to obtain reliable results.
Model : /workspace/checkpoints/en/
Audio : /workspace/sligo-triathlon-club-inviting-women-to-try-a-tri.mp3
Transcribing...

Transcription:
 we're going to talk triathlon right now on oceanfm sport because slago triathlon club are getting ready with their 2026 edition of the women's tria tri initiative and this is for female listeners if you've never tried a triathlon before this could be the time for you a 250 meter swim a 10 kilometer cycle and a 3km run we had the slagotriathland club in with us earlier this year for the men's triadri and now it's the turn of the women and in studio with me rosy dignam who's the women's officer for slagotriathland club and kirin maghann who is secretary of slagotri triathlon club folks thanks for coming in and rosa you were ideally placed to talk about this try a try initiative because you were one of the triers a couple of years ago yes...
 ```

## How it works

Whisper is an encoder-decoder transformer pretrained by OpenAI on 680,000 hours of multilingual audio. Fine-tuning adapts it to the acoustic style of a specific domain (in this case, FLEURS read speech) without training from scratch.

Each training job:
1. Converts audio to 80-channel log-mel spectrograms
2. Tokenizes transcriptions into Whisper's BPE vocabulary
3. Fine-tunes all model weights via cross-entropy loss with teacher forcing
4. Evaluates Word Error Rate (WER) on the validation set each epoch

On HPC, all five jobs run concurrently — wall-clock time equals one language, not five.

## Extending

**Add a language:** add entries to `LANGUAGE_CODES` and `FLEURS_CODES` in `train.py`, add the code to `LANGUAGES` in `submit.sh`, and expand `--array` to match.

**Use client audio data:** replace the `load_fleurs()` call in `train.py` with a custom `datasets.Dataset` — the rest of the pipeline is data-source agnostic.


## References:
https://huggingface.co/blog/fine-tune-whisper
