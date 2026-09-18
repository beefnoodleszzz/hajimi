---
name: blender-shot
description: Build reproducible Blender scenes for deterministic motion, scale, and camera work.
triggers: Blender, deterministic 3D, simulation, scientific animation
---

# Objective

Make scientific motion readable and repeatable through versioned Python scene
construction and preview renders.

# Inputs

Shot-local `shot.yaml`, storyboard, manifest dimensions, and reusable assets.

# Outputs

`build_scene.py`, `scene.blend`, preview render, full render, and render metadata.

# Required Workflow

1. Build from a clean scene with explicit renderer, camera, frame range, and FPS.
2. Use labelled layers and controlled materials.
3. Render at 25% preview first.
4. Record command, Blender version, and output hash.
5. Send preview through Fast QC before Resolve import.

# Quality Gate

Camera/motion/scale are deterministic, readable at 9:16, and no critical
relationship depends on model hallucination.

# Failure Conditions

Unscripted manual-only scene, unreadable labels, or final render without preview.

# Tools

Blender Python, `ffprobe`, `hajimi qc shot`.

# Forbidden Patterns

Do not use Cycles for a short proof when Eevee is sufficient; do not overwrite
accepted renders.

# Handoff

Pass render paths and hashes to `resolve-editor` and `fast-media-qc`.
