---
name: shot-designer
description: Write shot contracts and choose local image plus H3 production methods.
triggers: shot design, production method, shot brief, negative constraints
---

# Objective

Design the visual and motion contract before any generation. Local Hajimi owns
the story, image assets, prompts, continuity, and candidate selection.

# Required workflow

1. Translate the approved board into a Shot Contract covering narrative
   purpose, subject, environment, composition, camera, first/end states,
   lighting, continuity, and forbidden elements.
2. Use Codex image_gen locally for selected keyframes and references.
3. Choose among `ai_image`, `h3_i2v`, `h3_fl2v`, `h3_ref2v`, `hybrid_ai`,
   `fusion`, `footage`, and `animatic_card`.
4. Keep exact text, numbers, arrows, vectors, and tracked labels in Fusion or
   deterministic local graphics.
5. Bind the shot to its stable ID, active version, local inputs, hashes, H3
   duration/mode, ambience intent, and candidate count.
6. Review imported H3 candidates locally; remote workers never approve or
   select them.

# Failure conditions

A negative constraint, required keyframe, prompt, native-audio intent, or local
artifact path is missing; H3 is assigned narration or editing; or the route
cannot satisfy the story beat without a specified input.
