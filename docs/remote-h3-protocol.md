# Remote MiniMax H3 Worker Protocol

Hajimi is the source of truth. The remote worker renders only the submitted
video and native ambience; it does not rewrite prompts, select candidates, or
edit episode manifests. All JSON documents use UTF-8 and
`schema_version: hajimi-h3-remote-v1`.

## Job package

The local client creates `episodes/<episode>/remote_jobs/<job_id>/job.json` and
copies only selected source images into `assets/`. `input_sha256` contains one
SHA-256 digest for every asset referenced by `inputs`, and no other asset paths.
The worker must reject unsafe paths, missing files, changed hashes, unsupported
modes, and an incompatible schema before creating a ComfyUI prompt.

The supported modes are `i2va`, `fl2va`, and `ref2va`. Each job specifies a
candidate count, duration, aspect ratio, prompt, preservation/avoidance rules,
and `audio.generate_native_audio: true`. H3 ambience is required; narration and
music are never generated remotely.

## Worker commands

The client invokes the module configured in `config/remote_h3.yaml` over SSH:

```text
python3 -m hajimi_h3_worker doctor --json
python3 -m hajimi_h3_worker submit --job-dir <remote-job-directory> --json
python3 -m hajimi_h3_worker status --episode-id <episode-id> [--shot-id <shot-id>] --json
```

`doctor` returns an object with `schema_version`, `status: READY`,
`backend: minimax_h3`, and `checks`. A ready response requires all of these
checks to be `PASS`: `comfyui_api`, `h3_model`, `required_nodes`, and
`native_audio`. The local doctor independently checks SSH, the configured
runtime directory, and the ComfyUI API through remote localhost.

`submit` is idempotent by `job_id`. It returns the same schema version, the
submitted `job_id`, and one of `SUBMITTED`, `QUEUED`, `RUNNING`, `COMPLETE`, or
`FAILED`.
Repeating a job ID must return its existing state; a failed job is not retried
under the same ID.

`status` returns `schema_version` and a `jobs` array. Each entry contains
`job_id`, `episode_id`, `shot_id`, and one of `SUBMITTED`, `QUEUED`, `RUNNING`,
`COMPLETE`, or `FAILED`. Unknown jobs are omitted. The local client verifies
job/shot identity before updating `episode.yaml`.

## Result package

Completed results live at `<remote-root>/results/<job_id>/`:

```text
result.json
candidate_01.mp4
candidate_01.json
...
```

`result.json` contains `schema_version`, the matching `job_id`,
`status: COMPLETE`, `backend: comfyui_minimax_h3`, and exactly the requested
number of candidate records. Each record contains a unique `candidate_id`, a
safe local `filename`, and a safe `metadata_file` filename.

Each candidate sidecar contains `candidate_id`, `filename`, `sha256`,
`duration`, `width`, `height`, `fps`, `has_audio`, `audio_codec`, `sample_rate`,
`channels`, `workflow_id`, `workflow_version`, `h3_model_identity`, and
`generation_parameters`. Unavailable workflow fields are `null`; they must not
be guessed. The worker measures media fields from the produced file. The video
must contain both video and native audio streams.

The local client verifies candidate names, metadata types, hashes, ffprobe
stream facts, aspect ratio, and result identity before import. Local candidate
selection additionally requires a successful decode check and a named reviewer.
The remote worker never chooses a winner.

## Transport and storage boundary

ComfyUI listens only on remote `127.0.0.1`. SSH runs the worker and exposes no
public ComfyUI port. Use rsync when available and scp otherwise. Transfer only
the job package and pull only the result package; do not clone the repository,
embed media as base64, or commit generated video candidates.
