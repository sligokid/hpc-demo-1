## Parent PRD

`prd/task-2-company-brain/prd.md`

## Problem

Four files in `sync/input/en/` have been sitting unprocessed indefinitely and will never be picked up, because `.webm` is not in the configured extension list:

```
$ for f in sync/input/*/*; do case "$f" in *.done) continue;; esac; [ -f "$f.done" ] || echo "STUCK: $f"; done
STUCK: sync/input/en/Application_for_HPC_Access.webm
STUCK: sync/input/en/Eva Pascoal db4a185f-bd39-4055-a764-c3f7c460debb.webm
STUCK: sync/input/en/How_to_create_a_prototype_on_lovable.webm
STUCK: sync/input/en/Mobile_version_-_Slick__in_the_palm_of_your_hands_.webm
STUCK: sync/input/en/Workplace Learning Summit - Panel Full Talk.mp4
STUCK: sync/input/en/firedrill vid.mp4
```

(The last two are the inference bugs in issues 011 and 012.)

`pipeline.yaml:21` restricts discovery to:

```yaml
audio_extensions: [.mp3, .mp4, .wav, .flac, .m4a, .ogg]
```

`find_pending` (`pipeline.py:121-123`) skips any file whose suffix is not in that set, so the `.webm` files are invisible to the pipeline. They carry no `.done` sidecar, so nothing surfaces them as failures — they simply never appear in a manifest. The failure mode is silence, which is worse than an error: an operator has no way to know these four files were dropped.

**The extension list is duplicated in two places, and both must change.** `pipeline-hpc-submit.sh:43` hardcodes its own glob, independent of the YAML:

```bash
for f in "$dir"/*.{mp3,mp4,wav,flac,m4a,ogg}; do
```

So on the HPC path the manifest is built by the shell glob, and `pipeline.yaml`'s `audio_extensions` is only consulted by the `python pipeline.py` scan path. Adding `.webm` to just one of the two leaves the HPC poller still skipping the files. This duplication is itself the underlying defect — see the acceptance criteria.

`.webm` is a common screen-recording and webcam output format and is well within scope for a video knowledge pipeline. The container already has the FFmpeg-backed `audioread` path working for `.mp4` (the logs show `PySoundFile failed. Trying audioread instead.` followed by successful transcription), so `.webm` should decode without new dependencies.

## What to build

Add `.webm` to the pipeline's supported input formats so screen recordings and webcam captures are processed like any other upload.

- Add `.webm` to `audio_extensions` in `pipeline.yaml:21`.
- Add `.webm` to the glob in `pipeline-hpc-submit.sh:43`. **Both are required** — the HPC manifest is built by the shell glob, not the YAML.
- Better: remove the duplication. Have `pipeline-hpc-submit.sh` read the extension list from `pipeline.yaml` (it already parses `inbox:` from the file at line 21 via `grep`/`awk`), so there is a single source of truth. If that is too invasive, add a test asserting the two lists match.
- Verify the `audioread`/FFmpeg path in the container decodes `.webm` audio correctly. If `audioread` alone is insufficient, confirm whether `ffmpeg` is present in `whisper-hpc.sif` and route through it.
- Check whether `4-file-sync/sync.sh` filters extensions on the input leg — it currently does not appear to, but confirm, since the rclone `copy` will otherwise pull down any format regardless.
- Add a short note to `4-file-sync/README.md` listing the supported input formats and where that list is configured. PR #9 substantially expanded this file with "How it Works" and "Sample Output" sections, but added no supported-formats list, so the gap remains.

Then clear the backlog: once `.webm` is supported, the four stuck files should be picked up by the next `Z-poll` cycle without needing manual submission.

## Acceptance criteria

- [ ] `.webm` added to `audio_extensions` in `pipeline.yaml`
- [ ] `.webm` added to the glob in `pipeline-hpc-submit.sh`, or the duplication is removed so the YAML is authoritative
- [ ] A test asserts the extension list in `pipeline.yaml` and `pipeline-hpc-submit.sh` agree (if the duplication is not removed)
- [ ] `4-file-sync/sync.sh` verified to sync `.webm` files on the input leg
- [ ] At least one `.webm` file transcribes successfully end to end in the container
- [ ] All four currently-stuck `.webm` files are picked up by the poller and produce transcript, sentiment, analysis, and Qdrant index entries
- [ ] `4-file-sync/README.md` documents the supported input formats and points at the config location
- [ ] Unsupported extensions still fail silently rather than erroring — but the supported list is documented so this is discoverable

## Blocked by

- None - can start immediately

## Related

- `issues/013-bound-retry-loop-for-permanently-failing-files.md` — if any `.webm` turns out to be video-only, the no-audio guard and retry bound apply here too.

## User stories addressed

- Content captured by screen recorder or webcam is searchable like any other upload, with no manual intervention.
- An operator can determine from the documentation which formats the pipeline accepts.
- The supported-format list has exactly one source of truth, so it cannot disagree with itself.
