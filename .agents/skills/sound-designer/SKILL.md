---
name: sound-designer
description: Design layered VO, music, ambience, movement, impact, and silence for narrative clarity.
triggers: sound design, Fairlight, mix, music, SFX, ambience
---

# Objective

Make sound carry structure and physical direction instead of merely amplifying
a narration WAV.

# Inputs

Beat script, approved picture, narrator take, music/SFX/ambience library, and
manifest loudness targets.

# Outputs

Fairlight timeline/mix, stem manifest, ASR transcript, and loudness report.

# Required Workflow

1. Place VO and normalize intelligibility with EQ/compression/de-ess.
2. Add music curve, ambience bed, and 3–8 narrative SFX.
3. Use silence at information pivots when useful.
4. Check key numbers and duration against ASR.
5. Deliver `-14 LUFS` target and `-1 dBTP` ceiling.

# Quality Gate

VO, music, ambience, and SFX are independently identifiable and the mix does
not mask critical words.

# Failure Conditions

Bare VO, arbitrary loudness boost, clipping, or missing key number.

# Tools

Resolve Fairlight, FFmpeg ebur128/astats, faster-whisper when installed.

# Forbidden Patterns

Do not use audio to disguise a failed animatic or publish an un-QC'd master.

# Handoff

Pass mixed master and audio report to `final-master-qc`.
