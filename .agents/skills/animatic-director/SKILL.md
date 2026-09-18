---
name: animatic-director
description: Build and judge the low-cost storyboard animatic before production spend.
triggers: animatic, animatic gate, temp VO, temp SFX, pacing gate
---

# Objective

Prove story rhythm, mute readability, sound cadence, and hero-shot value before
AI video or expensive rendering.

# Inputs

Locked beat script, storyboard cards, temporary voice, music, and SFX.

# Outputs

Animatic MP4, gate JSON, contact sheet, and failed-check notes.

# Required Workflow

1. Assemble temp VO and layered temp sound.
2. Use simple camera movement and rough typography.
3. Check mute, audio-only, 1x, and 1.5x reads.
4. Check anomaly timing, visual-change cadence, and static holds.
5. Block production when the gate fails.

# Quality Gate

Gate is `PASS` only when the output decodes, has the required stems, has an
anomaly within 1.5 seconds, and includes a readable hero shot.

# Failure Conditions

Production started from a failed animatic or a narration-only timeline.

# Tools

`uv run hajimi animatic`, FFmpeg for mechanical render, contact sheet, Beads.

# Forbidden Patterns

Do not use generated production visuals to hide a weak story structure.

# Handoff

Pass only a PASS gate to `shot-designer`; keep failures in `animatic/gate.json`.
