---
name: final-master-qc
description: Perform deterministic, visual-sample, subtitle, ASR, audio, and integrity checks on a master.
triggers: master QC, final QC, release candidate, delivery check
---

# Objective

Decide whether a master is technically and editorially safe for private upload.

# Inputs

Master file, manifest, subtitle/story typography spec, audio report, and shot QC.

# Outputs

`qc/master_report.json`, human-readable report, and explicit PASS/FAIL decision.

# Required Workflow

1. Run deterministic metadata/decode and loudness checks.
2. Build proxy, scene/contact samples, and key-time screenshots.
3. Compare ASR with the locked script when ASR is available.
4. Verify geometry, safe-zone declaration, and media integrity.
5. Require one complete human playback before release.

# Quality Gate

No critical technical finding, dimensions/FPS/audio match manifest, and all
required checks are recorded.

# Failure Conditions

Missing master, wrong geometry, clipping, subtitle collision, unresolved shot
failure, or unrecorded human review.

# Tools

`uv run hajimi qc master`, FFmpeg, ASR, contact sheet.

# Forbidden Patterns

Do not re-direct the episode in final QC or publish on a missing report.

# Handoff

Pass only PASS to `youtube-publisher`; send failures back to the responsible role.
