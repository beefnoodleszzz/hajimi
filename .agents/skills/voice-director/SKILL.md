---
name: voice-director
description: Direct narrator performance and candidate selection for local VoxCPM2 production voice.
triggers: voice direction, narrator direction, voice plan, narration takes
---

# Objective

Decide how each beat should be spoken: energy, pace, emphasis, pauses, and
emotional intent. The role directs performance; it does not implement a TTS
engine.

# Production Policy

Use local VoxCPM2 through the `voxcpm2_local` adapter. The default main female
narrator is `science_female_main` in Ultimate mode, using the authorized local
reference. Do not auto-switch speaker or fall back to Qwen, cloud TTS, macOS
`say`, browser TTS, or another provider.

# Candidate Policy

Generate multiple takes only for hook, hero line, payoff, and ending. Keep one
main take for explanatory beats. Check clarity, pronunciation, numbers,
units, scientific terms, pacing, emotion, naturalness, noise, and script
accuracy before selection.

# Handoff

Write `audio/voice_plan.yaml` and `audio/voice_manifest.yaml`; Fairlight still
owns music, ambience, SFX, mix, and mastering.
