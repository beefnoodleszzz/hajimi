---
name: resolve-editor
description: Own the Resolve Edit, Fusion, and delivery handoff for picture rhythm and graphics.
triggers: Resolve, edit timeline, Fusion, picture edit, delivery
---

# Objective

Make Resolve the creative editor of record for trimming, pacing, compositing,
and export.

# Inputs

Approved shot renders, manifest, storyboard, temp/final audio, and handoff JSON.

# Outputs

Resolve project/timeline, Fusion graphics, render metadata, and master candidate.

# Required Workflow

1. Import only approved shots in manifest order.
2. Pass naked-cut pacing before decorative Fusion work.
3. Keep vectors, numbers, and story typography in Fusion.
4. Export with exact manifest dimensions/FPS/sample rate.
5. Send output to `final-master-qc`.

# Quality Gate

Naked cut works without effects; graphic labels are readable; output metadata
matches manifest and last accepted render is preserved.

# Failure Conditions

FFmpeg is used as a creative editor, unapproved media enters timeline, or no
readback render exists.

# Tools

DaVinci Resolve 21.1, Fusion, `resolve_sync_manifest.json`, FFmpeg delivery.

# Forbidden Patterns

Do not overwrite source media or claim Resolve mutation without evidence.

# Handoff

Pass master path and Resolve export metadata to `sound-designer` and `final-master-qc`.
