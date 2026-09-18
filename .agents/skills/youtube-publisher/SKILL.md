---
name: youtube-publisher
description: Safely prepare and execute YouTube Studio uploads through ego-browser with readback.
triggers: YouTube, publish, upload, Studio, visibility, AI disclosure
---

# Objective

Upload only a master that passed final QC, defaulting to PRIVATE and recording
all Studio state needed for later checks.

# Inputs

Private publish manifest, master QC PASS, master file, title/description,
audience choice, and AI disclosure decision.

# Outputs

`publish/youtube.json` with upload, metadata readback, checks, visibility, URL,
and schedule state.

# Required Workflow

1. Preflight all required fields and QC evidence.
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
