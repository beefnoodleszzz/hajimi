---
name: autodl-h3-worker
description: Operate Hajimi's AutoDL ComfyUI MiniMax H3 render worker, including instance inventory, SSH transfer, runtime checks, scoped cleanup, and smoke tests. Use for Hajimi AutoDL/H3 work, not unrelated cloud administration or creative production.
metadata:
  short-description: Operate Hajimi's AutoDL H3 worker
---

# Objective

Treat AutoDL as a remote MiniMax H3 render appliance for Hajimi. Creative
decisions, keyframes, narration, candidate selection, editing, and publishing
stay local. The remote side receives a prepared job and returns video with H3
native ambience plus runtime metadata.

# Read the current contract first

- `episodes/<episode>/episode.yaml` is the episode source of truth.
- `studio/remote/contract.py` defines the job package and
  `hajimi-h3-remote-v1` contract. `studio/remote/ssh_transport.py` and
  `studio/remote/h3.py` define the local SSH client behavior.
- Read `config/remote_h3.yaml` if present. The current client expects its
  schema to be `hajimi-remote-h3-v1`, ComfyUI to bind to remote localhost, and
  connection values to come from the configured environment variable names.
- Prefer `HAJIMI_H3_HOST`, `HAJIMI_H3_USER`, and `HAJIMI_H3_SSH_PORT` when
  available. Otherwise the project SSH client reads only `AUTODL_COMMAND` from
  `.env.local`, parses a direct `ssh` invocation as data, and forces BatchMode.
  Never source/eval the file, read or pass `AUTODL_PASSWORD`, or print the
  parsed command, host, or port.
- Check `hajimi --help` and the current package before using a command. Do not
  assume a CLI command or remote worker exists because a task brief describes
  the intended interface. If the active task is the full remote rebuild, also
  follow `/Users/zhangxiaolong/Desktop/AutoDL : ComfyUI : MiniMax H3 远程彻底清理与重构任务.md`.

# Connect and inventory

Use the existing keyless SSH configuration from the local Hajimi machine. Do
not print, `cat`, `source`, trace, or copy credential values from `.env.local`
into logs, prompts, configs, or reports. Prefer the project's configured SSH
transport. Do not pass a password when keyless SSH works. AutoDL's SCP
commands run on the local machine, not inside the remote shell.

Start each remote maintenance task with read-only checks and discover actual
paths instead of guessing:

```bash
hostname
pwd
df -h
du -xh --max-depth=2 /root/autodl-tmp 2>/dev/null | sort -h
du -xh --max-depth=2 /root/autodl-fs 2>/dev/null | sort -h
nvidia-smi
ps aux
```

Then locate ComfyUI, H3 weights and components, custom nodes, API workflows,
outputs, Python environment, and current processes. Record GPU model and VRAM
from the live instance; do not infer them from an older brief. Classify items as
`KEEP`, `DELETE`, or `VERIFY` and trace workflow/model/node dependencies before
marking anything for deletion.

# Local H3 job commands

Use these after `uv run hajimi h3 --help` confirms the commands. Run Doctor
before generation. A no-card instance is expected to fail the live GPU and
ComfyUI checks; do not change the instance GPU or billing state to force a pass.

```bash
uv run hajimi h3 doctor --json
uv run hajimi h3 prepare EP099_your-episode --shot S001 --json
uv run hajimi h3 submit EP099_your-episode --shot S001 --json
uv run hajimi h3 status EP099_your-episode --shot S001 --json
uv run hajimi h3 pull EP099_your-episode --shot S001 --json
uv run hajimi h3 select EP099_your-episode --shot S001 --candidate 1 --reviewer '<reviewer>' --json
```

`prepare` packages a manifest-approved shot, `submit` starts remote generation
and may incur usage charges, `pull` imports and validates results locally, and
`select` records a local candidate decision. Run `submit` only when the active
task authorizes generation. Do not select a candidate without local review.
After `pull` has validated and imported the result, the client sends the exact
`result.json` SHA-256 to the worker's guarded cleanup command. Never clean a
remote job before the local import and hash checks succeed.

# Storage and lifecycle

Read [AutoDL platform details](references/autodl-platform.md) when handling
storage, SSH, transfer, or instance lifecycle. In brief:

- `/root/autodl-tmp` is the high-IO instance data disk. It survives a system
  reset, but it is local storage without redundant copies.
- `/root/autodl-fs` is network file storage only when actually mounted. Verify
  the mount before relying on it; use it for small important configs, not H3
  inference or large model IO.
- AutoDL releases an instance after 15 consecutive days powered off; release
  removes its data. A running instance incurs usage charges.
- Never power-cycle, reset, release, resize, or change billing settings unless
  the current user task explicitly authorizes that exact operation.

# Cleanup boundaries

- Inventory before deletion. Keep the working ComfyUI environment, H3 model
  stack, required nodes, API workflows, and active worker configuration.
- Resolve every `VERIFY` item through workflow references, node imports,
  runtime logs, or a minimal safe dependency check. Do not guess based on file
  names.
- Delete only obsolete AI-production files within the scope authorized by the
  current task. Use exact paths and measured sizes; never use broad wildcard
  deletion or remove AutoDL system files, SSH keys/config, unrelated user data,
  or unknown content in `/root/autodl-fs`.
- Preserve a small recovery set of workflows, worker code, dependency/model
  manifests, and environment report in `/root/autodl-fs/hajimi-h3-backup/`
  only after confirming that file storage is mounted. Do not copy old projects,
  candidates, or bulk model weights there. Do not create an `archive/` dump.
- If a cleanup authorization is not present in the active task, report the
  exact proposed targets and wait before deleting them.

# Worker behavior

- Accept only the agreed `hajimi-h3-remote-v1` schema; reject a mismatched
  `schema_version`. Use `i2va`, `fl2va`, or `ref2va` only when the selected
  workflow supports the requested assets.
- Pass the local prompt through without remote creative rewriting. Patch only
  declared workflow inputs. Keep ComfyUI on `127.0.0.1` and access it through
  the worker/SSH path; never expose an unauthenticated public port.
- Generate one candidate at a time on the single GPU. Record a real seed only
  when the workflow exposes it; this worker writes its generated seed into the
  fixed RandomNoise input and candidate metadata.
- The deployed worker is under
  `/root/autodl-tmp/hajimi-h3-runtime/worker/`, with versioned API graphs in
  `workflows/`. Per-job runs patch declared values only; do not edit graph nodes
  or connections while preparing a job.
- Native H3 audio is part of the requested candidate. Do not add narration or
  music remotely. Record audio stream facts from `ffprobe`; do not claim
  semantic audio quality or choose a visual winner remotely.
- Return stable per-job result paths and metadata rather than relying on
  ComfyUI's internal output directory. Do not upload the whole repository or
  episode; transfer only the job JSON and referenced assets, and pull back only
  results and candidate metadata.
- Keep long-lived ComfyUI processes in an existing `screen` or `tmux` session
  and capture logs. Do not install packages or upgrade Python, Torch, CUDA,
  ComfyUI, or custom nodes just to make versions newer.

# Verify and hand off

1. Run the implemented local/remote Doctor only if the current CLI exposes it.
   Require its real checks to pass: SSH reachability, configured runtime path,
   ComfyUI localhost API, required H3 nodes/models, and protocol version. A
   no-card instance must retain a failed/blocked live readiness result; never
   synthesize a PASS or attach a GPU without explicit authorization.
2. For a new or changed stack, run one short, single-candidate smoke job with
   native audio. Check file existence, video/audio streams, duration, decode,
   metadata, and hashes with the project's tools and `ffprobe`.
3. Return candidates to the local episode flow for visual review and selection.
   Remote QC is machine-level only.
4. Delete a remote job directory only after the local pull/import and hashes
   have been verified, and only for that exact job ID.
5. Report detected environment, preserved/deleted locations and sizes, final
   runtime paths, workflow modes, Doctor/Smoke results, and blockers. Do not
   claim a remote operation ran unless its output was observed.

# AutoDL browser use

Use `ego-browser` only when a console page is needed to inspect instance state,
disk/mount status, or official help. Prefer the console's visible state and
official help over guessed URLs or hidden UI operations. Read the linked
platform reference before resetting, releasing, remounting, or changing an
instance; those actions are outside routine inventory.
