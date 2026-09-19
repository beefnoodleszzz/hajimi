---
name: ai-visual-producer
description: Adapt approved Hajimi shot direction and GPT Image skill recommendations into traceable local image prompt and candidate artifacts.
---

# Role

Be Hajimi's image production adapter. The upstream `gpt-image-2-style-library`
owns general GPT Image styles, templates, examples, and prompt guidance. Use its
recommendations to translate an already-decided visual intent into a final
Hajimi prompt; do not choose the story, hero shot, or visual thesis.

Consult `config/skill-routing.yaml` for the final image-stage route, required
upstream skill, and artifact locations.

# Inputs

- Passed animatic gate and approved Shot Contract at
  `episodes/<episode>/shots/<shot>/shot.yaml`.
- Selected visual direction, aspect ratio, reference pack, and continuity
  constraints from the episode artifacts.
- Image route and candidate budget from `generation-director`.
- Recommendations from `gpt-image-2-style-library` for the selected visual
  intent.

# Outputs

- Agent-authored final prompt at
  `episodes/<episode>/shots/<shot>/images/prompt.md` and structured companion
  metadata at `episodes/<episode>/shots/<shot>/images/prompt.json`.
- A local image job carrying that exact prompt, plus candidate files and JSON
  provenance under `episodes/<episode>/shots/<shot>/images/`.
- A director-selected keyframe path for the next production stage. Selection
  does not mean QC approval.

# Workflow

1. Read the Shot Contract and visual direction. Ask the upstream style library
   for matching style/template guidance; use only relevant recommendations.
2. Adapt them to the approved subject, composition, material, light, camera,
   continuity, aspect ratio, reference roles, and forbidden changes. Preserve
   exact text/number/annotation work for Fusion or deterministic graphics.
3. Save the final prompt and source recommendation/provenance before image
   generation. The prompt is an Agent artifact; do not use Python's generic
   prompt template as the creative source or silently replace the final prompt
   with it.
4. Use `studio/generation/image.py` for Hajimi job/path/hash/provenance duties
   where its interface preserves the Agent-authored prompt. Record the actual
   model/runtime facts available; never invent a seed.
5. Generate one candidate by default. Request a targeted variation only when
   review identifies a composition, continuity, or motion-readiness defect.
6. Present candidates for director selection. Pass the selected keyframe and
   its provenance to `generation-director` and, for an H3 route,
   `h3-video-director`.

# Failure Conditions

Stop if the animatic gate or Shot Contract is missing, the visual intent is
undecided, the upstream recommendation is unavailable, the prompt artifact
cannot be preserved byte-for-byte in the job/provenance, or a candidate would
violate a continuity or forbidden constraint. Do not generate production
images before the animatic passes.

# Handoff

Pass the selected keyframe and prompt/candidate provenance to shot QC and the
next routed production stage. Only QC-approved production media may enter the
roughcut. Keep H3 prompt writing with the upstream `h3-prompt-writing` skill;
this adapter does not write video prompts or submit remote jobs.
