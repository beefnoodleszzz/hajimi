---
name: resolve-editor
description: Apply optional DaVinci Resolve premium finishing to an existing Hajimi roughcut when the episode needs advanced picture or Fusion work.
---

# Role

Provide optional premium finishing after Hajimi's automatic FFmpeg roughcut.
FFmpeg remains the automatic roughcut editor and assembly executor. Use
DaVinci Resolve only when advanced pacing, Fusion, color, or Fairlight work is
needed; Resolve is not a prerequisite for an ordinary roughcut.

Consult `config/skill-routing.yaml` for the final optional-finish route and
handoff artifacts.

# Inputs

- `episode.yaml` and its ordered, approved shot media.
- The FFmpeg rough master and `edit/roughcut_manifest.json` when available.
- Sound and graphic intent plus manifest dimensions, FPS, and sample rate.

# Outputs

- A Resolve project/timeline and any requested Fusion or color work.
- A rendered premium-finish candidate and Resolve readback metadata using the
  project's configured handoff format (including `resolve_sync_manifest.json`
  when that path is active).
- No change to active episode state until the render/readback is reviewed and
  accepted through the project handoff.

# Workflow

1. Confirm premium finishing is requested or materially needed. If a complete
   FFmpeg roughcut already meets the brief, hand it to master QC without
   opening a Resolve edit.
2. Import only locally selected, approved media in episode order. Preserve
   `episode.yaml` as the timeline source of truth and retain the FFmpeg source
   render.
3. Review the naked cut before applying Fusion, color, or other finish work.
   Keep exact annotations in Fusion when they require deterministic placement.
4. Export at the episode's declared geometry, frame rate, and sample rate.
   Record the actual render and readback; never claim an unobserved Resolve
   change.
5. Send the accepted candidate to `final-master-qc`.

# Failure Conditions

Stop if the active media is unapproved, the source roughcut or manifest is
missing when needed, Resolve is unavailable, export settings conflict with
the episode contract, or no render/readback can be verified. Do not overwrite
the FFmpeg rough master or source media.

# Handoff

Pass the render path, project/timeline reference, and readback metadata to
`final-master-qc`. Use `config/skill-routing.yaml` for the optional finish
stage. FFmpeg remains the default automatic editor; Resolve is optional.
