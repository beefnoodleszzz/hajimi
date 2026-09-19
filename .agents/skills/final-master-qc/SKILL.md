---
name: final-master-qc
description: Perform deterministic, visual-sample, subtitle, ASR, audio, and integrity checks on a master.
---

# Objective

Decide whether an FFmpeg roughcut or optional Resolve premium-finish master is
technically and editorially safe for private upload.

# Inputs

Active master file and source/hash record, manifest, roughcut manifest when the
source is FFmpeg, subtitle/story typography spec, audio report, and shot QC.

# Outputs

`qc/master_report.json`, human-readable report, and explicit PASS/FAIL decision.

# Required Workflow

1. Identify `master.source`; run deterministic metadata/decode and loudness
   checks on the exact active master hash.
2. Build proxy, scene/contact samples, and key-time screenshots.
3. Compare ASR with the locked script when ASR is available.
4. Verify geometry, safe-zone declaration, and media integrity.
5. Require one complete human playback before release.

# Quality Gate

No critical technical finding, dimensions/FPS/audio match manifest, FFmpeg
roughcut provenance passes when applicable, Resolve readback passes when the
source is Resolve, and all required checks are recorded. Human playback must be
bound to the active master hash.

# Failure Conditions

Missing master, wrong geometry, clipping, subtitle collision, unresolved shot
failure, or unrecorded human review.

# Tools

`uv run hajimi qc master`, FFmpeg, ASR, contact sheet.

# Forbidden Patterns

Do not re-direct the episode in final QC or publish on a missing report.

# Handoff

Pass only PASS to `youtube-publisher`; send failures back to the responsible role.
