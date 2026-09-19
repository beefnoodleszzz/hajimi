---
name: reference-deconstructor
description: Deconstruct high-performing references into reusable shot and sound grammar.
---

# Objective

Measure references by time, cut, camera, sound, escalation, and loop—not by a
generic summary.

# Inputs

Reference videos or documented pattern observations, plus channel goal.

# Outputs

Structured JSON per reference and reusable YAML under `references/shot_patterns/`.

# Required Workflow

1. Identify the first anomaly and time-to-anomaly.
2. Mark cut points, average shot duration, visual peaks, and hero frame.
3. Record music, ambience, impacts, captions, and comment hook.
4. Separate observed evidence from creative inference.
5. Save compact structured data; do not load all references into context.

# Quality Gate

At least 5–10 references or an explicit documented pattern substitute are
available, and every conclusion has a timestamp or source note.

# Failure Conditions

Summary-only output, missing timing evidence, or copying a reference's assets.

# Tools

Media probe, proxy sampler, contact sheet, Beads.

# Forbidden Patterns

Do not prescribe the episode script or silently reuse source footage.

# Handoff

Deliver shot grammar to `creative-director` and `storyboard-director`.
