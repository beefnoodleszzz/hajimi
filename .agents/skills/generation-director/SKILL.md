---
name: generation-director
description: Route approved Hajimi shots to image, H3, Fusion, footage, or hybrid production and set bounded candidate budgets.
---

# Role

Decide how each approved Shot Contract should be produced. Own production
routing and resource choices only. The `storyboard-director` owns shot order
and composition; `shot-designer` owns the Shot Contract; upstream image/H3
skills own prompt craft; `h3-video-director` owns remote job operations.

Consult `config/skill-routing.yaml` for the final generation-stage route,
allowed methods, and plan location.

# Inputs

- Passed animatic gate and approved storyboard/Shot Contracts.
- Selected keyframes and references that exist locally, plus continuity,
  timing, factual, and forbidden constraints.
- Current capabilities from the configured image and H3 backends.

# Outputs

Write a per-shot generation plan under
`episodes/<episode>/production/generation_plan.yaml`, aligned with the stable
shot IDs and active contract versions. Record the production method, required
first/last/reference images, candidate budget, expected generation duration,
native ambience requirement, and deterministic graphics/footage needs.

# Workflow

1. Select among the methods supported by the current Hajimi contract:
   `ai_image`, `h3_i2v`, `h3_fl2v`, `h3_ref2v`, `hybrid_ai`, `fusion`,
   `footage`, or `animatic_card`.
2. Choose the minimum useful candidate budget: normally one for a connector,
   two or three for a story beat, and more for a hero only with a recorded
   reason and approved spend.
3. Record `edit_duration_sec` separately from `generation_duration_sec`. For
   MiniMax H3 at 24 fps, target at least 124 aligned frames (5.17 seconds) and
   no more than 362 aligned frames (15.08 seconds); split a longer shot. Let
   the H3 contract align frames. For a shorter edit slot, finish the central
   action within that slot's first 1.2–1.4 seconds, then hold a natural stable
   after-motion so FFmpeg can trim the raw candidate cleanly.
4. Preserve local-only selection: package only the selected keyframe and
   required references. Submit work incrementally after local review.
5. Route image prompt work to `ai-visual-producer` plus
   `gpt-image-2-style-library`; route H3 prompt work to `h3-prompt-writing`;
   route package/submit/status/pull/select to `h3-video-director`.

# Boundaries

Do not write image or H3 prompt text, prompt syntax, visual composition, shot
continuity, story direction, or FFmpeg commands. Do not silently change
backend, increase candidate count, or choose an unavailable model parameter.
H3 supplies video and native environmental audio only; it does not supply
narration, music, editing, or candidate selection.

# Failure Conditions

Return BLOCKED when the animatic gate failed, a required local reference is
missing, the shot contract cannot be satisfied by an available method, the
duration exceeds a verified backend limit, or the candidate budget lacks an
incremental justification.

# Handoff

Pass the validated production plan to `ai-visual-producer` for image routes or
`h3-video-director` for H3 operations. The latter packages only after the
prompt artifact and inputs are ready. Use `config/skill-routing.yaml` as the
final route map.
