---
name: ai-visual-producer
description: Produce traceable AI image/video candidates under shot-specific constraints.
triggers: AI image, AI video, prompt, visual candidate, generation
---

# Objective

Produce traceable AI candidates after the animatic gate. The current image
backend is Codex `image_gen` using GPT-Image 2 / 2.5. The current video backend
is Google Flow operated through `ego-browser`.

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
6. Send the selected keyframe and motion plan to `ai-video-director` for Flow.

# Quality gate

Candidate metadata is complete, direction/identity are stable, and Fast QC is
PASS or explicitly REVIEW with a director decision. Exact numbers, labels,
arrows, vectors, and scientific annotations belong in Fusion.

# Handoff

Pass approved candidate and provenance JSON to `resolve-editor`.
