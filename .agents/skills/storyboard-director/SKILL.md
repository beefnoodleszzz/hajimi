---
name: storyboard-director
description: Translate beats into shot-level composition, lens, motion, continuity, and risk.
triggers: storyboard, shot list, composition, lens, continuity
---

# Objective

Make every beat filmable and explain what information, emotion, or rhythm the
shot contributes.

Organize the board into HERO, STORY, and CONNECTOR shots. HERO shots deserve
the strongest composition and generation budget; STORY shots carry factual or
causal information; CONNECTOR shots preserve momentum and continuity.

# Inputs

Locked beat script, creative brief, brand language, and production capabilities.

# Outputs

Versioned storyboard YAML with one record per stable shot ID.

# Required Workflow

1. Set composition, lens, height, camera motion, subject motion, and screen direction.
2. Specify transitions and sound events.
3. Select Blender/Fusion/AI/footage with a risk note.
4. Preserve continuity anchors across shots.
5. Delete any shot whose removal has no cost.
6. Give every shot a stable ID, visual role, information payload, and a
   measurable change from the previous shot.

# Quality Gate

Hero shot reads as a still, direction is consistent, and every shot has an
expected duration and production method. No shot may be a narration-only
placeholder.

# Failure Conditions

Unmotivated inserts, reversed direction, unresolved subject identity, or no
transition rationale.

# Tools

Storyboard YAML, contact sheets, manifest, Beads.

# Forbidden Patterns

Do not generate final AI assets before the animatic gate.

# Handoff

Deliver storyboard and risk register to `animatic-director` and `shot-designer`.
