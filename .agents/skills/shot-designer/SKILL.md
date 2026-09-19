---
name: shot-designer
description: Author Hajimi Shot Contracts with continuity state and one visible action per shot.
---

# Role

Be the Shot Contract author and continuity adapter. Use the approved board's
stable shot IDs. Apply relevant continuity and cinematography methods from
`short-drama-agent`; do not import its provider-specific production workflow.

Consult `config/skill-routing.yaml` for the final shot-contract stage,
artifact path, and downstream route.

# Inputs

- Approved storyboard shot order and composition notes.
- Visual concept, beat purpose, information payload, and factual constraints.
- Previous/next shot state, references, subject/environment identity, and
  production constraints.

# Output

Write `episodes/<episode>/shots/<shot>/shot.yaml`, bound to the stable shot ID
and active version. Keep manifest identity and routing fields at the root;
place visual/motion constraints in the nested `shot_contract` mapping. Include
the current contract's required `visual_goal`, `first_frame`, `end_frame`,
lighting, palette, continuity, and `forbidden` fields, plus the relevant
continuity details for this shot:

- `narrative_purpose`, `information_payload`, subject, environment, and
  composition;
- camera height/lens feel, lighting, subject/environment/camera motion;
- start and end state, screen direction, previous and next shot;
- `continuity_receive`, `continuity_handoff`, identity/environment locks, and
  prop state;
- first/last/tail-frame requirements, `preserve`, `avoid`, audio intent, and
  edit/generation duration.

Use empty/null values only where the active schema allows them; record a reason
for optional continuity fields that do not apply. Leave root `method`, motion
route, and candidate budget for `generation-director` to decide.

# Workflow

1. Translate each board card into a contract that states what carries into the
   shot, what visibly changes, and what state passes to the next shot.
2. Default to one primary visible action per H3 shot. Split a sequence when
   it requires multiple major actions, locations, or camera events.
3. Keep composition/camera consistent with the board. Add preserve/avoid
   constraints that protect identity, screen direction, environment, and
   critical props.
4. Make first, last, and tail-frame requirements concrete enough for image/H3
   specialists to use. Do not author their prompt text.

# Failure Conditions

Fail if the stable ID/version is ambiguous, a shot has no information or
narrative purpose, multiple primary actions cannot be separated, adjacent-shot
state conflicts, or required continuity/frame constraints are unresolved.

# Handoff

Pass `shot.yaml` to `generation-director` for method routing. Image prompt work
goes to `ai-visual-producer`; H3 prompt craft goes to `h3-prompt-writing` and
job operations to `h3-video-director`. The final artifact and routes are
registered in `config/skill-routing.yaml`.
