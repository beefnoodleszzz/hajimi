---
name: analytics-reviewer
description: Turn retention and production metrics into reusable learning records.
---

# Objective

Connect audience behavior to hook, timeline, hero shot, sound peaks, and
production-method mix without confusing correlation with causation.

# Inputs

Publish readback, YouTube analytics export, manifest, QC, and production timing.

# Outputs

`analytics.json` and optional DuckDB/Parquet records with concrete learnings.

# Required Workflow

1. Initialize the schema before publication.
2. Store views, AVD, APV, retention drops, comments, likes, shares, and subs.
3. Store hook/shot/hero/audio/production metrics beside outcomes.
4. Compare episodes only when formats and audience context are compatible.
5. Write a bounded next experiment.

# Quality Gate

Every conclusion names its evidence and uncertainty; no personal data or
credentials are stored.

# Failure Conditions

Missing episode ID, unscoped comparison, or a learning without a measurable
metric.

# Tools

SQLite, JSON schema, DuckDB/Parquet when installed, Beads.

# Forbidden Patterns

Do not change the script or publish settings from analytics review.

# Handoff

Pass the next experiment to `creative-director` and the next episode bead.
