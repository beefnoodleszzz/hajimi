# Hajimi Studio Agent Operating Manual

## Mission

Hajimi is an AI-driven visual storytelling studio.

Primary objective: produce world-class knowledge-entertainment Shorts and
long-form videos for `The World You Never Knew`.

Optimization order:

1. audience retention
2. visual storytelling quality
3. factual correctness
4. sound and editing quality
5. repeatability
6. automation speed

Never optimize production speed by sacrificing the first four.

## Non-Negotiable Rules

- Do not patch the legacy V1 production system or create compatibility folders.
- `episodes/<episode>/episode.yaml` is the single source of truth.
- Every shot has one stable shot ID and one active version in the manifest.
- No production-quality shot is generated before the animatic passes.
- FFmpeg is mechanical media infrastructure, not the creative editor.
- DaVinci Resolve is the primary picture and sound editor.
- Deterministic scientific motion prefers Blender/Fusion.
- AI video must pass shot QC before entering the timeline.
- Never QC every frame with an LLM/VLM.
- Always run deterministic QC first and reuse results for unchanged hashes.
- Every expensive action must be incremental and reproducible.
- Never publish without final-master-qc PASS.

## Required Workflow

```text
topic
→ research
→ creative brief
→ reference deconstruction
→ script beats
→ storyboard
→ animatic
→ animatic gate
→ shot production
→ shot QC
→ edit
→ sound
→ master
→ master QC
→ upload private
→ YouTube checks
→ publish/schedule
```

Stages may not be skipped. If a stage is unavailable, record `skipped` and the
reason in the episode manifest or `.amv/project-state.json`.

## Quality Targets

- anomaly or result inside 1.5 seconds
- meaningful visual change every 1–3 seconds
- visual/audio peak every 8–12 seconds
- at least one hero shot
- no static AI plate held over 4 seconds without a written justification
- no narration-only mix
- no unresolved visual artifact in an approved shot

## QC Policy

Fast QC hierarchy:

1. ffprobe / decode / black / freeze / silence
2. 540p proxy
3. scene detection
4. 3-frame-per-shot sampling
5. cheap CV metrics
6. contact sheet
7. VLM only for representative or suspicious frames
8. human/director review when required

Never reverse this order. A hash and QC profile version identify reusable QC
results in SQLite.

## Tool Responsibilities

- Blender: deterministic 3D, simulations, controlled cameras.
- AI image/video: hero visuals, impossible imagery, controlled plates.
- Resolve: editing, pacing, Fusion, Fairlight, delivery.
- FFmpeg: proxy, extraction, analysis, encode, deterministic QC.
- ego-browser: logged-in website interaction and YouTube Studio publishing.
- Beads: durable task tracking and production blockers.

## Agent Skill Routing

Use project skills under `.agents/skills/`:

- creative direction → `creative-director`
- reference analysis → `reference-deconstructor`
- factual research → `research-editor`
- script beats → `short-script-editor`
- storyboard → `storyboard-director`
- animatic → `animatic-director`
- shot method → `shot-designer`
- Blender environment/bootstrap → `blender-bootstrap`
- Blender shot production, preview, render QC → `blender-production`
- AI generation → `ai-visual-producer`
- edit → `resolve-editor`
- sound → `sound-designer`
- shot QC → `fast-media-qc`
- master QC → `final-master-qc`
- YouTube upload → `youtube-publisher`
- analytics → `analytics-reviewer`

Do not silently combine unrelated roles.

## Beads

Use `bd` for all durable task tracking. Every production blocker must be
represented as a bead. Do not use markdown TODO files as the canonical tracker.

## Destructive Operations

The V1 production architecture was explicitly scoped for removal by the
rebuild request. Do not delete `.git` or `.beads`. After rebuild begins, never
restore V1 folders into the active tree.

## Publish Safety

Default YouTube visibility is `private`. The agent may prepare metadata and
record a publish preflight. It must not make a video public or scheduled unless
the current task explicitly authorizes that action and supplies the schedule.

Never store cookies, tokens, or account credentials in the repository.

## Completion Protocol

Before closing an episode, confirm:

- manifest is consistent;
- all active shots are approved;
- master exists;
- master QC is PASS;
- title/description package exists;
- upload result and YouTube checks are recorded;
- analytics record is initialized.

At session close, run quality gates, update the relevant Beads issue, and
report changed files, validation, and any external step that was not executed.
