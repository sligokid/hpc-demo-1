# Sync Pipeline Setup Guide

End-to-end setup for the Google Drive ↔ LUMI HPC sync pipeline. Follow these steps once per user / per machine. After setup the pipeline runs automatically via a self-resubmitting SLURM job.

---

## Prerequisites

- Docker installed locally (with `buildx` support)
- `rclone` installed locally (`brew install rclone` on macOS)
- SSH access to LUMI (`ssh lumi`)
- A Google account

---

## 1. Create a GCP project and enable the Drive API

The sync uses Google's Drive API via OAuth2. You need a GCP project to obtain OAuth2 credentials — this is free and does not require billing.

1. Go to [console.cloud.google.com](https://console.cloud.google.com) and create a new project (e.g. `whisper-sync`).
2. In the left menu, go to **APIs & Services → Library**.
3. Search for **Google Drive API** and click **Enable**.

---

## 2. Create OAuth2 credentials

1. Go to **APIs & Services → Credentials** and click **+ Create Credentials → OAuth client ID**.
2. If prompted, configure the OAuth consent screen first:
   - User type: **External**
   - App name: anything (e.g. `whisper-sync`)
   - Add your Google account email as a test user
3. Back in Create Credentials:
   - Application type: **Desktop app**
   - Name: anything (e.g. `rclone`)
4. Download the JSON file — you'll need the **Client ID** and **Client Secret** in the next step.

---

## 3. Configure rclone on your local machine

Run the interactive config wizard:

```bash
rclone config
```

Follow the prompts:

```
n) New remote
name> gdrive

Storage type> drive          # Google Drive

client_id>     <paste your Client ID from step 2>
client_secret> <paste your Client Secret from step 2>

scope> 1                     # Full access to all files

root_folder_id>              # leave blank
service_account_file>        # leave blank

Edit advanced config> n
Use auto config> y           # opens a browser for OAuth login
```

A browser window opens. Log in with your Google account and grant access. rclone saves the refresh token automatically.

Lock down the config file:

```bash
chmod 600 ~/.config/rclone/rclone.conf
```

Verify the remote works:

```bash
rclone lsd gdrive:
```

You should see your Google Drive root folders listed.

**Token lifetime:** Google refresh tokens remain valid indefinitely as long as the remote is used at least once every 6 months. The 5-minute polling schedule on LUMI keeps the token alive automatically.

---

## 4. Create the Drive folders

Create the two sync folders in Google Drive. rclone will not create top-level folders automatically.

```bash
rclone mkdir gdrive:whisper-sync/input
rclone mkdir gdrive:whisper-sync/output
```

Verify:

```bash
rclone lsd gdrive:whisper-sync
```

---

## 5. Test locally with Docker

### 5a. Mock remote test (no credentials needed)

Build the image and run the full sync test against a local mock remote:

```bash
# From the project root
./3-sync/test-sync.sh          # tests sync.sh directly (requires rclone on PATH)
./3-sync/docker/test-local.sh  # tests the full Docker image end-to-end
```

Both should print `✓ All tests passed`.

### 5b. Live test against real Google Drive

Once the rclone config is set up (steps 1–4), run the container against your actual Drive folders to confirm credentials work end-to-end before deploying to LUMI.

Build the image for your local architecture (faster than cross-compiling):

```bash
docker build --tag whisper-sync 3-sync/
```

Create local landing directories:

```bash
mkdir -p /tmp/whisper-sync/input /tmp/whisper-sync/output /tmp/whisper-sync/logs
```

Run one sync cycle against real Google Drive:

```bash
docker run --rm \
    -v ~/.config/rclone:/config/rclone:ro \
    -v /tmp/whisper-sync:/workspace \
    -e WORKSPACE=/workspace \
    -e RCLONE_REMOTE=gdrive \
    -e DRIVE_INPUT=gdrive:whisper-sync/input \
    -e DRIVE_OUTPUT=gdrive:whisper-sync/output \
    whisper-sync
```

What to check after it runs:

```bash
# Any files in Drive input/ should appear here
ls /tmp/whisper-sync/input/

# The manifest lists newly arrived files
cat /tmp/whisper-sync/logs/sync-manifest.txt

# The per-run log
cat /tmp/whisper-sync/logs/sync-*.out
```

Drop a test file into `gdrive:whisper-sync/input/` via the Google Drive web UI, re-run the `docker run` command, and confirm it appears in `/tmp/whisper-sync/input/`.

> **Note:** The rclone config is mounted read-only (`:ro`). The container cannot modify or leak your credentials.

---

## 6. Build the Docker image for linux/amd64

The SIF must be built from a `linux/amd64` image regardless of your local architecture:

```bash
docker buildx build \
    --platform linux/amd64 \
    --load \
    --tag whisper-sync \
    3-sync/
```

---

## 7. Convert to SIF

**On macOS**, `singularity build` requires a Linux environment. Use [Lima](https://github.com/lima-vm/lima) or [Colima](https://github.com/abiosoft/colima):

```bash
# Install Colima if not already installed
brew install colima

# Start a Linux VM with Docker socket forwarding
colima start --arch x86_64

# Build the SIF inside the VM (Apptainer/Singularity must be in the VM)
# Alternatively: push to Docker Hub and build the SIF directly on LUMI (see Option B below)
singularity build whisper-sync.sif docker-daemon://whisper-sync:latest
```

**Option B — push to Docker Hub and build on LUMI (simpler on macOS):**

```bash
# Locally
docker tag whisper-sync your-dockerhub-user/whisper-sync:latest
docker push your-dockerhub-user/whisper-sync:latest

# On LUMI
singularity build \
    /scratch/project_465003209/mcgowank/whisper-sync.sif \
    docker://your-dockerhub-user/whisper-sync:latest
```

---

## 8. Upload the SIF to LUMI

If you built the SIF locally (Option A above):

```bash
scp whisper-sync.sif lumi:/scratch/project_465003209/mcgowank/whisper-sync.sif
```

Verify it is there:

```bash
ssh lumi ls -lh /scratch/project_465003209/mcgowank/whisper-sync.sif
```

---

## 9. Copy the rclone config to LUMI

```bash
scp ~/.config/rclone/rclone.conf lumi:~/.config/rclone/rclone.conf
ssh lumi chmod 600 ~/.config/rclone/rclone.conf
```

---

## 10. Start the polling chain on LUMI

SSH into LUMI, navigate to the sync job directory, and submit:

```bash
ssh lumi
cd /scratch/project_465003209/mcgowank/hpc-demo-1/3-sync/hpc
sbatch submit-sync.sh
```

The job runs one sync cycle and resubmits itself on exit. The chain continues indefinitely until you cancel it.

---

## 11. Verify the chain is running

```bash
# Check the job is queued or running
squeue -u $USER

# Watch the latest sync log
tail -f /scratch/project_465003209/mcgowank/hpc-demo-1/logs/sync-*.out | head -50

# Check the manifest for arrived files
cat /scratch/project_465003209/mcgowank/hpc-demo-1/logs/sync-manifest.txt
```

To stop the chain:

```bash
scancel <jobid>
```

---

## 12. Stop and restart

The chain stops if you cancel the job or if `sbatch` itself fails (rare). To restart:

```bash
cd /scratch/project_465003209/mcgowank/hpc-demo-1/3-sync/hpc
sbatch submit-sync.sh
```

---

## Swapping cloud provider

All cloud provider config is isolated to two places: the rclone remote definition in `~/.config/rclone/rclone.conf` and the two env vars in `3-sync/hpc/submit-sync.sh`. No script logic changes.

### Switch to Google Cloud Storage (GCS)

1. Add a GCS remote to `~/.config/rclone/rclone.conf`:

```ini
[gcs]
type = google cloud storage
project_number = your-gcp-project-number
object_acl = private
bucket_acl = private
```

2. In `3-sync/hpc/submit-sync.sh`, update the env vars:

```bash
export RCLONE_REMOTE=gcs
export DRIVE_INPUT=gcs:your-bucket-name/whisper-sync/input
export DRIVE_OUTPUT=gcs:your-bucket-name/whisper-sync/output
```

### Switch to AWS S3

1. Add an S3 remote to `~/.config/rclone/rclone.conf`:

```ini
[s3]
type = s3
provider = AWS
access_key_id = YOUR_ACCESS_KEY
secret_access_key = YOUR_SECRET_KEY
region = eu-west-1
```

2. In `3-sync/hpc/submit-sync.sh`, update the env vars:

```bash
export RCLONE_REMOTE=s3
export DRIVE_INPUT=s3:your-bucket-name/whisper-sync/input
export DRIVE_OUTPUT=s3:your-bucket-name/whisper-sync/output
```

No Dockerfile changes, no `sync.sh` changes.
