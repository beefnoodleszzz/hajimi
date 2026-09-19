---
name: h3-video-director
description: Prepare, submit, inspect, and hand off locally directed ComfyUI MiniMax H3 jobs.
triggers: H3 job, remote video generation, candidate pull, H3 shot selection
---

# Objective

Keep all creative direction and candidate selection in local Hajimi. AutoDL is
only a remote ComfyUI + MiniMax H3 render worker that returns video with native
environment audio.

# Required workflow

1. Confirm the animatic production gate passed and review the canonical
   `episode.yaml` plus the shot's Shot Contract.
2. Confirm selected local keyframes and all references exist. Use
   `uv run hajimi h3 prepare <episode> --shot S001` to package the contract and
   hashed image assets. Preparation never submits work.
3. Run `uv run hajimi h3 doctor` before network operations. ComfyUI must listen
   only on remote localhost and be reached through SSH; never expose port 8188.
4. Submit only the shot the local director selected with
   `uv run hajimi h3 submit <episode> --shot S001`.
5. Poll with `uv run hajimi h3 status <episode> --shot S001`, then pull the
   completed result locally with `uv run hajimi h3 pull <episode> --shot S001`.
6. Validate `result.json`, each candidate sidecar, hashes, video/audio streams,
   metadata, and decode locally. Unknown workflow/model fields stay null.
7. Inspect candidates locally with representative frames and audio. Never let
   the remote worker choose a winner. Select explicitly with
   `uv run hajimi h3 select <episode> --shot S001 --candidate 1 --reviewer <name>`.
8. Run `uv run hajimi qc shot <episode> S001` on the selected candidate. If
   Fast QC returns REVIEW, record the director decision with
   `uv run hajimi qc review <episode> S001 --decision PASS --reviewer <name>`.
   Only a QC-approved shot may enter the roughcut.
9. Keep VoxCPM2 narration as the only production narration. Reject or mute H3
   dialogue, narration, or music that conflicts with the shot contract.

# Protocol boundary

- Contract version: `hajimi-h3-remote-v1`.
- Modes: `i2va`, `fl2va`, and `ref2va`.
- Local paths, prompt, duration, candidate count, preserve/avoid rules, and
  native-audio intent are authored before upload.
- The worker may render, probe, and return candidates. It cannot edit manifests,
  approve a candidate, change the episode, or publish.
- Credentials remain in environment variables or SSH configuration. Job
  packages contain only contracts and required approved keyframes.

# Failure conditions

Stop if the contract version differs, a path escapes the job package, an input
hash changes, a native-audio stream is missing, metadata disagrees with
ffprobe, or deterministic decode fails. Never retry an expensive job without a
new local decision.
