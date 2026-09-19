---
name: shot-designer
description: Choose an AI-first production method and write Shot Contracts.
triggers: shot design, production method, shot brief, negative constraints
---

# Objective

Design the cinematic AI visual first, then preserve factual clarity through
composition, continuity, and Fusion overlays. Scientific accuracy is not a
requirement to run an engineering simulation.

# Required workflow

1. Translate the approved board into one Shot Contract: intent, subject,
   environment, composition, camera, first/end frame, motion, lighting,
   continuity, and forbidden constraints.
2. Default to Codex image_gen keyframe first, then Google Flow I2V.
3. Use multi-keyframe generation for distinct states; split complex changes.
4. Defer exact text, numbers, arrows, vectors, and labels to Fusion.
5. Record backend/model/reference fields; never invent an unavailable seed.
6. Bind outputs to the active shot ID, version, input hashes, and local artifact paths.

# Failure conditions

AI is used for exact vectors/text; a negative constraint or local artifact path
is missing; or candidate counts, acceptance criteria, or retry boundaries are
undefined.

# Handoff

Pass the Shot Contract to `ai-visual-producer`, `ai-video-director`, or
`resolve-editor`.
