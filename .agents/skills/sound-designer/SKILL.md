---
name: sound-designer
description: Turn Hajimi beats and approved picture into sound intent and executable episode cue artifacts.
---

# Role

Design sound to clarify physical action, emotion, and information changes.
Own sound intent and cue artifacts; execution may use Hajimi's FFmpeg roughcut
or optional Resolve/Fairlight finishing. Fairlight is not required for the
ordinary FFmpeg path. Production narration remains local VoxCPM2.

Consult `config/skill-routing.yaml` for the final sound-stage route and artifact
locations.

# Inputs

- Validated beat script and storyboard timing/sound events.
- Approved picture and its H3 native environmental audio.
- Selected VoxCPM2 narration and voice direction from `voice-director`.
- Episode music/SFX assets and manifest loudness targets.

# Outputs

- Episode sound-intent and cue plan at the audio artifact path configured in
  `config/skill-routing.yaml`.
- Supported local execution settings in `episodes/<episode>/edit/roughcut.yaml`:
  music path/gain, SFX paths/times/gain, subtitles, and text overlays.
- A handoff note for cues that need an optional Resolve/Fairlight pass or
  cannot be represented by Hajimi's current roughcut contract.

Preserve H3 native ambience unless the Shot Contract says it should be muted.
Do not imply that a plan produced a separate stem or Fairlight timeline unless
that artifact was actually rendered and recorded.

# Workflow

1. Derive sound events from the locked beats, picture, and shot audio intent.
   Keep VoxCPM2 narration as the production voice source.
2. Place music, ambience, silence, and SFX cues against the episode timeline.
   Use upstream editing guidance only for capabilities relevant to this
   Hajimi artifact contract.
3. Map cues expressible by the current FFmpeg roughcut into
   `edit/roughcut.yaml`. The roughcut preserves H3 ambience, mixes narration,
   music, and optional SFX, applies sidechain music ducking, subtitles/text
   overlays, and manifest loudness targets.
4. Record unsupported timing/mix intent for optional premium finishing instead
   of claiming the FFmpeg adapter executed it.
5. Pass the roughcut to Fast QC and then final-master QC for measured audio and
   output checks.

# Failure Conditions

Fail handoff if a cue conflicts with the beat/shot contract, narration is not
the selected local VoxCPM2 production audio, required asset paths are missing,
or the mix plan cannot fit the episode timeline. Do not use music/SFX to hide
a failed animatic or unreadable picture.

# Handoff

Pass the sound plan and supported `roughcut.yaml` settings to
`ffmpeg-rough-editor` for automatic assembly. Pass any requested premium
Fairlight work to `resolve-editor`. Send the rendered master and audio evidence
to `final-master-qc`. The final stage and artifact paths are in
`config/skill-routing.yaml`.
