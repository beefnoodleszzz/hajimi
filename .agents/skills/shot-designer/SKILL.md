---
name: shot-designer
description: Choose the appropriate production method and write constraints for each shot.
triggers: shot design, production method, shot brief, negative constraints
---

# Objective

Select the cheapest method that preserves the shot's intent and physics.

Translate the approved board into a generation plan and a shot contract:
method, candidate count, reference inputs, negative constraints, acceptance
criteria, and regeneration policy. The contract must preserve the shot's
visual role and information payload.

# Inputs

Approved storyboard, animatic gate, asset availability, and manifest.

# Outputs

Shot-local `shot.yaml` with method, intent, constraints, risks, and output paths.

# Required Workflow

1. Ask whether motion, scale, or camera must be exact.
2. Prefer Blender/Fusion for deterministic science.
3. Use licensed footage for real-world evidence.
4. Reserve AI video for controlled impossible or atmospheric visuals.
5. Record prompt/reference/model/seed fields for AI candidates.
6. Allocate production-quality generation only after the animatic gate; keep
   candidate exploration cheap and reproducible.
7. Bind outputs to the active shot ID, version, and input hashes.

# Quality Gate

No shot is sent to AI solely because it is visually attractive; method matches
the information risk.

# Failure Conditions

AI is used for exact vectors, text, or physics; no negative constraint; no hash.
The generation plan is missing a tier, candidate count, acceptance criterion,
or retry boundary.

# Tools

Manifest, Blender/Fusion handoffs, asset registry, Beads.

# Forbidden Patterns

Do not approve a shot or edit the timeline.

# Handoff

Pass shot briefs to `blender-production`, `ai-visual-producer`, or `resolve-editor`.
