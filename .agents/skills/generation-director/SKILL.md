---
name: generation-director
description: Route visual shots across local Codex image_gen, remote ComfyUI MiniMax H3, Fusion, footage, and hybrid production.
triggers: generation plan, shot routing, candidate competition, regeneration strategy
---

# Objective

Choose a shot-specific image and H3 route that protects story clarity,
continuity, factual payload, and candidate budget. Hajimi owns every decision.

# Responsibilities

- Decide whether a shot needs a first frame, last frame, or additional local
  reference images.
- Choose `h3_i2v`, `h3_fl2v`, `h3_ref2v`, `hybrid_ai`, `fusion`, `footage`, or
  `animatic_card` from the real shot requirements.
- Set the shot duration, H3 prompt, native ambience intent, candidate count,
  preserve/avoid rules, and continuity anchors.
- Route all keyframes and reference images to local Codex image_gen.
- Route video and native environmental audio to remote ComfyUI MiniMax H3.
- Use one candidate for a connector, two or three for a story beat, and reserve
  larger candidate budgets for a hero shot when review justifies them.

# Rules

- Package only locally selected keyframes and required references; never upload
  rejected image candidates.
- H3 is not a narration, music, research, edit, or selection provider.
- Keep exact numbers, labels, vectors, and annotations in Fusion or simple
  deterministic local graphics.
- Prepare jobs before any remote submission. Submit incrementally after local
  review; never launch a mechanical batch.
- Treat unavailable model parameters as unknown. Do not invent seeds, workflow
  versions, or backend capabilities.
