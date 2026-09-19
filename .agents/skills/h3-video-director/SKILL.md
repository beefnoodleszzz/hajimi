---
name: h3-video-director
description: Prepare, submit, inspect, and hand off locally directed ComfyUI MiniMax H3 jobs.
---

# Objective

Keep all creative direction and candidate selection in local Hajimi. AutoDL is
only a remote ComfyUI + MiniMax H3 render worker that returns video with native
environment audio.

# Required workflow

1. Confirm the animatic production gate passed and review the canonical
   `episode.yaml` plus the shot's Shot Contract.
2. Confirm selected local keyframes and all references exist. Keep the episode
   timeline's `edit_duration_sec` separate from `generation_duration_sec`:
   MiniMax H3 renders at least 124 aligned frames (about 5.17 seconds) and no
   more than 362 aligned frames (about 15.08 seconds). Split a shot that needs
   more time. For a short edit slot, direct the central action to finish inside
   the slot's first 1.2–1.4 seconds, then hold a natural stable after-motion so
   FFmpeg can trim the raw candidate without cutting off the story action.
3. Load the official `h3-prompt-writing` skill and author the complete final
   prompt locally from the Shot Contract, Motion Plan, keyframes, continuity,
   timeline, and explicit audio intent. Record it unchanged with
   `uv run hajimi h3 prompt-record <episode> --shot S001 --prompt-file <final-prompt.txt> --revision <n>`.
   Then run `uv run hajimi h3 prepare <episode> --shot S001`; Python validates
   and packages the prompt artifact but does not rewrite it. Preparation never
   submits work.
4. Run `uv run hajimi h3 doctor` before network operations. ComfyUI must listen
   only on remote localhost and be reached through SSH; never expose port 8188.
5. Submit only the shot the local director selected with
   `uv run hajimi h3 submit <episode> --shot S001`.
6. Poll with `uv run hajimi h3 status <episode> --shot S001`, then pull the
   completed result locally with `uv run hajimi h3 pull <episode> --shot S001`.
7. Validate `result.json`, each candidate sidecar, hashes, video/audio streams,
   metadata, and decode locally. Unknown workflow/model fields stay null.
8. Inspect candidates locally with representative frames and audio. Never let
   the remote worker choose a winner. Select explicitly with
   `uv run hajimi h3 select <episode> --shot S001 --candidate 1 --reviewer <name>`.
9. Run `uv run hajimi qc shot <episode> S001` on the selected candidate. If
   Fast QC returns REVIEW, record the director decision with
   `uv run hajimi qc review <episode> S001 --decision PASS --reviewer <name>`.
   Only a QC-approved shot may enter the roughcut.
10. Keep VoxCPM2 narration as the only production narration. Reject or mute H3
   dialogue, narration, or music that conflicts with the shot contract.

# Protocol boundary

- Contract version: `hajimi-h3-remote-v1`.
- Modes: `i2va`, `fl2va`, and `ref2va`.
- The prompt is the unchanged contents of `shots/Sxxx/h3/prompt.txt`, bound by
  `prompt.json` to its Shot Contract and keyframe hashes. `job.json` is transport
  packaging only; the remote worker passes `job.prompt` unchanged to MiniMax H3.
- Native environment audio intent is in `overall_soundscape`; default
  `non_diegetic_music` is `N/A`. H3 receives no production narration or dialogue.
- The worker may render, probe, and return candidates. It cannot edit manifests,
  approve a candidate, change the episode, or publish.
- Credentials remain in environment variables or SSH configuration. Job
  packages contain only contracts and required approved keyframes.

# Failure conditions

Stop if the contract version differs, a path escapes the job package, an input
hash changes, a native-audio stream is missing, metadata disagrees with
ffprobe, or deterministic decode fails. Never retry an expensive job without a
new local decision.
