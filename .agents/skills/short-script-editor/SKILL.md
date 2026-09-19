---
name: short-script-editor
description: Convert upstream short-form script craft and Hajimi direction into a validated beat-script-v2 artifact with hook and mute-read decisions.
---

# Role

Be Hajimi's beat-script schema and gate adapter. `short-form-video-script`
owns general retention craft; `creative-director` owns the final creative
direction and hook choice. Capture their work in Hajimi's contract instead of
repeating their general methods.

Consult `config/skill-routing.yaml` for the final script-stage route, required
inputs, and artifact location.

# Inputs

- Research fact pack and claim references from `research-editor`.
- Creative brief and tournament direction from `creative-director` and
  `idea-tournament`.
- Script-craft result from `short-form-video-script`, including distinct hook
  options and a proposed beat sequence.
- Episode duration, language, and manifest constraints.

# Outputs

Write `episodes/<episode>/creative/beat_script.yaml` with
`schema_version: beat-script-v2`, the selected hook, hook competition, mute
read result, and timed beats. Each beat carries `id`, `purpose`, `narration`,
`visual_action`, `visual_information`, `camera_event`, `sound_event`,
`emotional_change`, `duration_target`, `visual_role`, and `fact_refs`.

`hook_competition` records 3–5 materially different alternatives. Each
alternative states its visual event, verbal hook, and screen-information hook;
the set must differ in the audience-facing idea or event, not just wording.
Record the selected alternative and the creative director's rationale.

`mute_read` records PASS/FAIL, what the viewer understands without audio, the
first visible event, whether cognition changes within three seconds, and any
revision needed. This decision is required before script lock.

# Workflow

1. Consume upstream craft output and the approved direction. Do not recreate
   generic hook, loop, or retention theory.
2. Preserve factual claims and attach `fact_refs` to the beats that use them.
   Convert the script into the beat schema without changing the intended
   direction silently.
3. Capture the 3–5 distinct hook options and selected combination. If the
   upstream result or creative direction does not provide real alternatives,
   return for hook development instead of manufacturing near-duplicate lines.
4. Run the MUTE READ before lock: check that the first image contains an event,
   core change is understandable with sound off, and visuals advance the idea
   without narration. A failure returns to script or visual design.
5. Validate all beat fields and duration targets against the current episode
   contract, then hand off the artifact.

# Failure Conditions

Fail handoff for missing or unsupported `fact_refs`, a missing beat field,
fewer than three or more than five distinct hook options, an unresolved mute
read, narration with no visual action/information, or a script that exceeds
the episode's approved duration. Do not lock a failed artifact.

# Handoff

Pass the validated `beat_script-v2` and hook/mute-read records to
`storyboard-director`. Pass the locked narration and beat purposes to
`voice-director` and sound intent to `sound-designer`. The final project route
and consumer paths are recorded in `config/skill-routing.yaml`.
