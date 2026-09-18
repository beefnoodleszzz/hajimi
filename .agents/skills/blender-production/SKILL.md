---
name: blender-production
description: Build deterministic cinematic Blender shots for Hajimi when a shot needs reproducible 3D, scientific motion, or controlled camera work.
---

# Objective

Create reproducible, cinematic, physically legible Blender shots for Hajimi.
Blender is a deterministic visual backend, not the final editor.

# Inputs

- the episode manifest and shot-local brief
- storyboard intent and screen direction
- approved local assets and their license metadata
- the project Blender config and render profiles

# Required workflow

1. Decide whether Blender is the correct method for the shot.
2. Build from a clean scene using the Hajimi camera rig and named collections.
3. Lock composition at P0 before adding detail or baking expensive simulation.
4. Keep Eevee as the default; use Cycles only with a written shot reason.
5. Render a P1 image-sequence proxy before any production-quality render.
6. Run deterministic representative-frame QC and reuse hash-matched results.
7. Render final as PNG/OpenEXR image sequence, never as final MP4.
8. Write render metadata and handoff information for Resolve.

# Camera and performance rules

- Animate CameraRoot/Dolly/PanTilt/Shake/Target controls, not dozens of direct camera channels.
- Preserve the storyboard screen direction and the 9:16 safe guides.
- Instance repeated environment assets; use low-density scatter and low-volume quality in preview.
- Do not bake high-quality simulation before camera approval.
- Use local curated assets first; online/vendor assets require source and license metadata.

# QC and forbidden behavior

- Pre-render checks must pass before Blender is invoked for a render.
- Inspect first/middle/last representative frames and a proxy; never send every frame to a VLM by default.
- A changed scene/script/asset/plugin hash invalidates dependent cache entries.
- Do not install, download, or bypass licenses for commercial add-ons.
- Do not add a plugin merely for a generic “cinematic” effect.
- Do not use Blender for final subtitles, music, sound design, or delivery editing.

# Output

`blender/generated/artifacts/<shot>/` contains the scene, shot config, preview, final image sequence, QC report, cache, logs, and Resolve handoff manifest.

# Handoff

Return renderer, profile, frame range, output path, hashes, QC decision, dependency status, and any blocked baseline or plugin items.
