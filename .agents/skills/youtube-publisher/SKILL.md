---
name: youtube-publisher
description: Safely prepare and execute YouTube Studio uploads through ego-browser with readback.
---

# Objective

Upload only a master that passed final QC, defaulting to PRIVATE and recording
all Studio state needed for later checks.

# Inputs

Private publish manifest, source-specific master provenance, master QC PASS,
hash-bound human playback, master file, title/description, audience choice,
and AI disclosure decision.

# Outputs

`publish/youtube.json` with upload, metadata readback, checks, visibility, URL,
and schedule state.

# Required Workflow

1. Preflight metadata, shot approval/QC/provenance, production VoxCPM2,
   hash-bound master QC and human review. For an FFmpeg master, require the
   roughcut manifest, current hashed inputs, and an output hash matching the
   active master; Resolve readback is `NOT_APPLICABLE`. For a Resolve master,
   require a passing Resolve readback as well.
2. Create an independent ego-browser task space.
3. Use `snapshotText()` to discover current controls; use `uploadFile()`.
4. Fill metadata, read it back, disclose altered/synthetic content truthfully.
5. Upload PRIVATE, wait non-blockingly for checks, record states and URL.

# Quality Gate

No guessed selectors/metadata, no credentials in repo, and no visibility change
to Public/Scheduled without current explicit authorization.

# Failure Conditions

Missing QC, guessed made-for-kids/AI setting, bypassed checks, or cookie scraping.

# Tools

ego-browser skill, `publish.yaml`, `youtube.json`, Beads.

# Forbidden Patterns

Do not implement Playwright login/cookie capture, use private YouTube APIs, or
make a video public by default.

# Handoff

Pass Studio readback and checks to `analytics-reviewer`.
