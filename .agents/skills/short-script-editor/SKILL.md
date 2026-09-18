---
name: short-script-editor
description: Convert research into a timed beat script with hook, escalation, payoff, and loop.
triggers: script, beat sheet, voiceover, shorts rewrite
---

# Objective

Write a filmable beat sequence where each sentence has one punch and each
visual changes the audience's mental model.

Write visual-first: every beat needs a concrete visual action, the information
that action reveals, and a reason the audience must keep watching. Voiceover
supports the image; it must not be used to excuse a static plate.

# Inputs

Fact pack, creative brief, duration, and channel typography rules.

# Outputs

Versioned beat script under `episodes/<episode>/script/` with time, voice,
visual, sound, and purpose per beat.

# Required Workflow

1. Put anomaly/result in the first 1.5 seconds.
2. Keep one sentence to one punch; say numbers once.
3. Escalate from personal to system scale.
4. Correct the most likely misconception.
5. Earn a loop or comment question.
6. Label each beat's visual role and tie it to the storyboard's HERO, STORY, or
   CONNECTOR hierarchy.

# Quality Gate

Mute-readable beats, 1–3 second visual change plan, 34–38 second target for
EP001, and every claim links back to research. Each beat exposes a
`visual_action` and an `information_change` that can be checked without audio.

# Failure Conditions

Intro before event, paragraph narration, redundant conversions, or a false
question with no real options.

# Tools

Manifest, fact pack, ASR diff after audio exists.

# Forbidden Patterns

Do not reuse legacy wording or write visuals that can only be a static plate.

# Handoff

Hand the locked beat script to `storyboard-director` and `sound-designer`.
