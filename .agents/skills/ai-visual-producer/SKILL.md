---
name: ai-visual-producer
description: Produce traceable AI image/video candidates under shot-specific constraints.
triggers: AI image, AI video, prompt, visual candidate, generation
---

# Objective

Generate controlled candidates that serve an approved shot intent and preserve
continuity anchors.

# Inputs

Passed animatic, shot brief, reference assets, model configuration, and brand language.

# Outputs

Candidate media plus JSON recording model, prompt, references, seed, date, and
source hash.

# Required Workflow

1. Read shot constraints before writing a prompt.
2. Keep text, vectors, exact measurements, and physics out of generated plates.
3. Generate candidates only after the animatic gate passes.
4. Run deterministic and continuity QC on every candidate.
5. Let the director select; do not self-approve by novelty.

# Quality Gate

Candidate metadata is complete, direction/identity are stable, and Fast QC is
PASS or explicitly REVIEW with a director decision.

# Failure Conditions

Missing seed/model/reference, model-generated text, or unexplained continuity drift.

# Tools

Configured model providers, local hash/QC tools, asset registry.

# Forbidden Patterns

Do not send un-QC'd media to Resolve or silently reuse legacy V1 assets.

# Handoff

Pass approved candidate and provenance JSON to `resolve-editor`.
