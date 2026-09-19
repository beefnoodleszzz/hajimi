---
name: ai-video-director
description: Operate the real Google Flow UI through ego-browser and register local video candidates.
triggers: Google Flow, AI video, I2V, text-to-video, multi-keyframe, video candidate
---

# Objective

Turn an approved Shot Contract, selected keyframe, reference pack, and motion
plan into traceable local Google Flow candidates. The current video backend is
Google Flow operated through the project's `ego-browser` browser automation.

# Required workflow

1. Confirm the animatic gate and read `shots/Sxxx/shot.yaml`.
2. Open the real Google Flow page with `ego-browser` and confirm the user is
   logged in. Do not invent an API endpoint, SDK, or key.
3. Choose the declared mode: `image_to_video`, `text_to_video`,
   `multi_keyframe_video`, variation, extension, or repair.
4. Upload the selected keyframe and continuity references using visible labels,
   accessible roles, and semantic selectors; tolerate UI layout changes.
5. Enter only the motion prompt: subject/environment/camera motion, timing,
   state changes, preserve, and avoid constraints.
6. Wait for the real page preview, inspect it, and download each candidate to
   `episodes/<episode>/shots/Sxxx/video/`.
7. Register the local file with `backend: google_flow_browser`,
   `generation_mode`, source image, prompt, downloaded file, SHA-256, and any
   page-visible model/duration/aspect ratio. Record unavailable fields as
   `unknown`; never guess.
8. A candidate cannot be approved unless the local downloaded file and its
   provenance sidecar exist. Fast QC and director selection remain separate.

# Motion rules

Image prompts describe what the frame looks like. Flow prompts describe what
changes over time. Prefer first-frame plus strong end-state prompt when the UI
does not expose a last-frame control. Split KF1 → Video A → KF2 → Video B → KF3
when one task would require too many state changes.

# Handoff

Pass only locally downloaded, QC-reviewed, director-selected video and its
provenance to `resolve-editor`. Exact graphics belong in Fusion.
