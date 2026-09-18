---
name: fast-media-qc
description: Run the cached five-tier media QC funnel without flooding agent context.
triggers: Fast QC, media QC, proxy, contact sheet, shot check
---

# Objective

Find technical and likely visual failures quickly through deterministic,
incremental evidence.

# Inputs

Shot/master media, manifest, QC config, and SQLite cache.

# Outputs

`report.json`, `report.md`, contact sheets, metrics, suspicious-frame paths, and
cache records keyed by SHA-256 + profile version.

# Required Workflow

1. Tier 0: ffprobe, decode, black, freeze, silence, ebur128, astats.
2. Tier 1: 540p proxy, preferably hardware decode on macOS.
3. Tier 1.5: AdaptiveDetector scene detection.
4. Tier 2: 2 samples for short shots, otherwise 10/50/90 percent per scene.
5. Tier 3: VLM only on contacts/suspicious frames.
6. Tier 4: director/human review when required.

# Quality Gate

Unchanged hash/profile reuses cache; first pass never sends complete video to a
VLM; failures name location, evidence, and decision.

# Failure Conditions

Full-frame VLM review, source-resolution first pass, or cache bypass.

# Tools

`uv run hajimi qc`, FFmpeg, PySceneDetect, Pillow/OpenCV optional, SQLite.

# Forbidden Patterns

Do not inspect thousands of frames sequentially or approve a failed Tier 0 asset.

# Handoff

Pass PASS/REVIEW/FAIL plus contact sheet to `final-master-qc` or the director.
