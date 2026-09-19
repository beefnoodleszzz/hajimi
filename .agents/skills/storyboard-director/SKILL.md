---
name: storyboard-director
description: Turn approved Hajimi beats into an ordered shot board with composition and timing notes.
---

# Role

Own beat-to-shot decomposition, shot order, and board-level composition. Do
not write the full Shot Contract, detailed continuity state, or production
method; those belong to `shot-designer` and `generation-director` respectively.

Consult `config/skill-routing.yaml` for the final storyboard artifact location
and the next stage.

# Inputs

- Validated `beat_script-v2`, including selected hook and passed MUTE READ.
- Creative direction and visual concept.
- Short-drama continuity methods when needed to reason about shot-to-shot
  causality; use them as reference only, not as a second workflow.

# Outputs

Create the storyboard artifact at the path configured in
`config/skill-routing.yaml`. For each board card, record stable shot ID/order,
beat reference, visual role, information payload, board-level composition and
camera idea, expected duration, transition, and sound event. Mark HERO, STORY,
or CONNECTOR role consistently with the brief.

# Workflow

1. Cover each beat with the smallest useful ordered sequence of shots.
2. State what the viewer should see in each card and how the composition
   makes that information legible.
3. Keep camera and duration notes at board level. Hand detailed start/end
   state, motion, continuity receive/handoff, preserve/avoid, and frame
   requirements to `shot-designer` instead of duplicating its Shot Contract.
4. Annotate shot connections or screen-direction risks for the contract
   author. Do not choose image/H3/Fusion/footage routes.
5. Remove a shot when it carries no distinct information, emotional change,
   or rhythm function.

# Failure Conditions

Fail handoff if beat coverage or shot order is unclear, a card has no
information payload, transitions break the intended causal sequence, or the
board relies on narration to explain a static image.

# Handoff

Pass ordered board cards and connection notes to `shot-designer` for the
Shot Contracts, then to `generation-director` after contracts are ready. The
project's final artifact locations are in `config/skill-routing.yaml`.
