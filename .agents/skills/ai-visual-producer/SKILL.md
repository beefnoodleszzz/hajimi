---
name: ai-visual-producer
description: Produce traceable AI image/video candidates under shot-specific constraints.
triggers: AI image, AI video, prompt, visual candidate, generation
---

# Objective

Produce traceable AI candidates after the animatic gate. The current image
backend is local Codex `image_gen`. The video backend is remote ComfyUI
MiniMax H3 through Hajimi's SSH contract. VoxCPM2 remains the only production
narration provider.

# Required workflow

1. Read the Shot Contract and reference pack before writing a prompt.
2. Compile image prompts around identity, composition, camera, lighting,
   materials, depth, aspect ratio, continuity anchors, and forbidden constraints.
3. Generate exactly one image candidate per shot by default. Inspect it and
   continue; request a targeted variation only when the candidate fails
   composition, continuity, or motion-potential review.
4. Register every local Codex result under `shots/Sxxx/images/` with JSON
   provenance. Never invent a seed when the runtime does not expose one.
5. Let the director select `selected_keyframe.png`; selection is not QC approval.
6. Send the selected keyframe and motion plan to `generation-director` and
   `h3-video-director` for a shot-specific H3 route. Keep publishing browser
   work separate from video generation.

# Quality gate

Candidate provenance is complete and identity/direction are stable. Selecting
an H3 candidate does not approve it: run shot Fast QC and record a director
review when the QC result requires one. Exact numbers, labels, arrows, vectors,
and scientific annotations belong in Fusion.

# Handoff

Pass the locally selected candidate and provenance to shot QC; send approved
shots to the `video-editing` workflow or optional `resolve-editor` finish.
