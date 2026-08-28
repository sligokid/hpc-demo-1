# SLICK+ HPC Demo — Multilingual Whisper Fine-Tuning for ASR

**Goal: Turning videos into machine-readable knowledge**

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
### Transcription Example
```
mcgowank@uan18:~/scratch/mcgowank/hpc-demo-1> bash infer-on-gpu.sh
srun: job 21352183 queued and waiting for resources
srun: job 21352183 has been allocated resources
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

### Translation ES -> En Example
```
mcgowank@uan18:~/scratch/mcgowank/hpc-demo-1> bash infer-translate-on-gpu.sh
srun: job 21352472 queued and waiting for resources
srun: job 21352472 has been allocated resources
/opt/conda/envs/py_3.10/lib/python3.10/site-packages/transformers/models/whisper/generation_whisper.py:509: FutureWarning: The input name `inputs` is deprecated. Please make sure to use `input_features` instead.
  warnings.warn(
You have passed task=translate, but also have set `forced_decoder_ids` to [[1, 50259], [2, 50359], [3, 50363]] which creates a conflict. `forced_decoder_ids` will be ignored in favor of task=translate.
The attention mask is not set and cannot be inferred from input because pad token is same as eos token. As a consequence, you may observe unexpected behavior. Please pass your input's `attention_mask` to obtain reliable results.
Model : /workspace/checkpoints/es/
Audio : /workspace/spanish-telephone-phrases.mp3
Translating...

Translation:
 hello or hello who is speaking? from whom? speak Guillermo one moment I would like to talk to Guillermo she is not at home can I leave a message no está en casa puedo dejarle un recado sabe usted cuando regresa? yo le hablo por yo le hablo para atrás luego puede hablar más despacio se encuentra guillermo I speak back later. Can I speak more slowly? Is Guillermo here? I am busy. Can I speak later?
```

## Metadata Generation

`analyze.py` takes a transcript and calls an Ollama LLM to extract structured metadata (title, description, tags, goals, skills).

### Local — native Ollama on GPU 

Serve llama
```bash
ollama serve          # in a separate terminal, if not already running
ollama pull llama3.1:8b # once

# OR instead 
ollama run llama3.1:8b
```

Query llama
```bash
python analyze.py --transcript transcripts/my-video.txt
```

Pipe from `infer.py` directly:

```bash
python infer.py --model_dir checkpoints/en --audio my-talk.mp3 | \
    python analyze.py --transcript -
```

### Local — Docker Compose on CPU only (no native Ollama install required)

```bash
# 1. Start the Ollama service
docker compose up -d ollama

# 2. Pull the model into the named volume (once)
docker compose exec ollama ollama pull llama3

# 3-a. Run analyze.py inside the dev container
docker compose run --rm dev python analyze.py     --transcript results/infer-on-gpu.sh.txt     --ollama-host ollama:11434

# 3-b. Run analyze.py against ollama runnning in a docker container
python analyze.py     --transcript results/infer-on-gpu.sh.txt

# 3-c Run analyze.py against ollama runnning locally
python analyze.py     --transcript results/infer-on-gpu.sh.txt --model llama3.1:8b
```

The `ollama_models` named volume persists model weights across restarts. Re-running step 2 after the model is cached is safe and fast.

> **Note:** Docker Desktop on macOS cannot access Apple Metal (MPS). Ollama inside Docker uses CPU inference only. For faster results, use native Ollama (`ollama serve`) and point `analyze.py` at `localhost:11434` (the default).

### Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--transcript` | required | Path to transcript file, or `-` to read from stdin |
| `--model` | `llama3` | Ollama model to use |
| `--ollama-host` | `localhost:11434` | Ollama host to connect to |

### Swap the model

Any model pulled into the named volume can be used:

```bash
docker compose exec ollama ollama pull mistral
docker compose run --rm dev python analyze.py \
    --transcript transcripts/my-video.txt \
    --ollama-host ollama:11434 \
    --model mistral
```

### HPC — Ollama on GPU node (AMD/ROCm)

Runs `analyze.py` at scale: a persistent Ollama service occupies one GPU node and serves
the whole batch, eliminating per-task model-load overhead (~30–60 s each).

#### Prerequisites — build `ollama.sif` once

On a login node or data-transfer node with internet access:

```bash
# Set cache dirs to avoid leaving temp files on the login node
mkdir -p /tmp/$USER
export SINGULARITY_TMPDIR=/tmp/$USER
export SINGULARITY_CACHEDIR=/tmp/$USER

singularity pull ollama.sif docker://ollama/ollama:rocm
mv ollama.sif /scratch/project_465003209/$USER/
```

#### Step 1 — pull model weights into scratch (once, before air-gapped compute)

Run on any node with internet access while the Ollama service is already running:

```bash
./ollama/hpc/3-ollama-pull.sh              # pulls llama3 (default)
./ollama/hpc/3-ollama-pull.sh llama3:8b-q4 # or a quantised variant
```

The script verifies the model is present in `ollama list` before exiting.

#### Step 2 — start the persistent Ollama service

```bash
mkdir -p logs
SVC=$(sbatch --parsable ollama/hpc/2-ollama-serve-sbatch.sh)
echo "Service job: $SVC"
```

The job writes `hostname:11434` to the endpoint discovery file in scratch once the
HTTP health check passes. It removes the file on exit (wall-time expiry or `scancel`).

#### Step 3 — submit the batch analysis array

```bash
N=$(find transcripts/ -name "*.txt" | wc -l)
sbatch --dependency=after:$SVC --array=0-$((N-1)) analyze-batch.sh transcripts/
```

Each task reads the endpoint file, calls `analyze.py --transcript <file> --ollama-host
<endpoint>`, and writes JSON to `metadata/<basename>.json`.

#### Interactive single-transcript (srun wrapper)

```bash
./analyze-on-gpu.sh transcripts/foo.txt
```

#### Unattended overnight pipeline — chain all steps in one command

```bash
# 1. Start the Ollama service and capture the job ID
SVC=$(sbatch --parsable ollama/hpc/2-ollama-serve-sbatch.sh)

# 2. Submit batch analysis — starts only after the service job is allocated
N=$(find transcripts/ -name "*.txt" | wc -l)
sbatch --dependency=after:$SVC --array=0-$((N-1)) analyze-batch.sh transcripts/

echo "Service job $SVC — analysis array queued behind it"
```

#### Directory layout

```
/scratch/project_465003209/<user>/
    ollama.sif          # Ollama Singularity image (built once)
    ollama-models/      # GGUF weight cache (written by ollama-pull.sh)
    ollama.endpoint     # hostname:port — created on service start, removed on exit

$PWD/
    transcripts/        # input:  one .txt per video (from infer.py)
    metadata/           # output: one .json per transcript (from analyze.py)
    logs/               # SLURM stdout/stderr  (%A_%a.out convention)
```

## Pipeline Overview

```
┌─────────────────────────────────────────────────────────┐
│  TRAINING  (HPC — 5 parallel SLURM jobs)                │
│                                                         │
│  Google FLEURS  ──►  train.py  ──►  checkpoints/<lang>  │
│  (en, es, fr,         x5 GPUs                           │
│   zh-CN, ar)          in parallel                       │
└─────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────┐
│  TRANSCRIPTION  (local or HPC)                          │
│                                                         │
│  audio file  ──►  infer.py  ──►  transcript (text)      │
│                   (Whisper)                             │
└─────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────┐
│  METADATA GENERATION  (local — Ollama)                  │
│                                                         │
│  transcript  ──►  analyze.py  ──►  metadata (JSON)      │
│                   (llama3)         title, description,  │
│                                    tags, goals, skills  │
└─────────────────────────────────────────────────────────┘
```

## How it works

Whisper is an encoder-decoder transformer pretrained by OpenAI on 680,000 hours of multilingual audio. Fine-tuning adapts it to the acoustic style of a specific domain (in this case, FLEURS read speech) without training from scratch.

Each training job:
1. Converts audio to 80-channel log-mel spectrograms
2. Tokenizes transcriptions into Whisper's BPE vocabulary
3. Fine-tunes all model weights via cross-entropy loss with teacher forcing
4. Evaluates Word Error Rate (WER) on the validation set each epoch

On HPC, all five jobs run concurrently — wall-clock time equals one language, not five.

### How translation works — and why it has limits

Whisper's decoder is conditioned on two special tokens at the start of every output sequence: a **language token** and a **task token** (`<|transcribe|>` or `<|translate|>`). Switching `--task translate` swaps the task token, instructing the decoder to produce English text instead of reproducing the source language.

**Why the checkpoints weren't fine-tuned for translation:**
The five checkpoints in this project were trained exclusively with `task=transcribe` — the decoder was always asked to reproduce the source-language text. The translation head (the weights that map from `<|translate|>` to English tokens) was never updated during fine-tuning; it retains OpenAI's pretrained values.

**What this means in practice:**
- Transcription quality benefits from fine-tuning on FLEURS. Translation quality does not — it reflects `openai/whisper-small`'s pretrained translation capability, which is weaker than its transcription capability, especially for `whisper-small`.
- Mixed-language output (as seen in the ES→EN example above) is a known failure mode: the model partially reverts to the source language mid-sequence. This is more common with `whisper-small` and with languages that were less represented in Whisper's pretraining data.
- Translation always outputs **English only** — Whisper's translate task is English-output only. There is no arbitrary source→target language pair support.
- The `forced_decoder_ids` conflict warning printed at runtime is harmless: the checkpoint's baked-in `generation_config` sets `forced_decoder_ids` for transcription mode, but passing `task=translate` via `generate_kwargs` overrides it correctly.

**To get higher-quality translation:** upgrade to `openai/whisper-large-v3` (change `MODEL_ID` in `train.py`) for better pretrained translation capability, or fine-tune explicitly in translation mode by setting `task="translate"` in `train.py` and providing paired audio + English reference transcripts (FLEURS includes these).

## Extending

**Add a language:** add entries to `LANGUAGE_CODES` and `FLEURS_CODES` in `train.py`, add the code to `LANGUAGES` in `submit.sh`, and expand `--array` to match.

**Use client audio data:** replace the `load_fleurs()` call in `train.py` with a custom `datasets.Dataset` — the rest of the pipeline is data-source agnostic.


## References:
https://huggingface.co/blog/fine-tune-whisper
https://www.learn-spanish-faster.com/articles/spanish-phrases-free-mp3-download.html

