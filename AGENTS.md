# Hajimi Studio Agent Operating Manual

## Mission

Hajimi is an AI-driven visual storytelling studio.

Primary objective: produce world-class knowledge-entertainment Shorts and
long-form videos for `The World You Never Knew`.

Optimization order:

1. topic quality
2. creative angle
3. visual storytelling
4. factual correctness
5. generation quality
6. voice performance
7. editing / sound
8. repeatability
9. automation speed

Never optimize production speed by sacrificing the first four.

## Non-Negotiable Rules

- Do not patch the legacy V1 production system or create compatibility folders.
- `episodes/<episode>/episode.yaml` is the single source of truth.
- Every shot has one stable shot ID and one active version in the manifest.
- No production-quality shot is generated before the animatic passes.
- FFmpeg builds the complete local rough cut from approved H3 shots and local audio assets.
- DaVinci Resolve is optional premium finishing for advanced pacing, Fusion, color, and Fairlight.
- Deterministic graphics and exact annotations prefer Fusion; cinematic motion prefers AI image/video.
- AI video must pass shot QC before entering the timeline.
- Never QC every frame with an LLM/VLM.
- Always run deterministic QC first and reuse results for unchanged hashes.
- Every expensive action must be incremental and reproducible.
- Never publish without final-master-qc PASS.
- Production narration MUST use the local VoxCPM2 voice workstation.
- The default main female voice is `science_female_main`, using the authorized
  local reference and VoxCPM2 Ultimate mode. Do not silently switch to Qwen,
  cloud TTS, macOS `say`, browser TTS, or another speaker.
- Temporary animatic voice is `TEMP_ONLY` and `NOT_FOR_MASTER`.

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

- Codex image_gen: AI image concepts, references, keyframes, variations, and shot first/end frames.
- AutoDL ComfyUI + MiniMax H3: remote video and native environmental audio rendering only.
- Fusion: exact text, numbers, arrows, vectors, tracked graphics, masks, and compositing.
- FFmpeg: local rough-cut assembly, audio mix, subtitle burn-in, proxy, extraction, analysis, encode, and deterministic QC.
- Resolve: optional premium edit, color, Fusion, Fairlight, and delivery polish.
- ego-browser: logged-in YouTube Studio or other publishing/website operations; never video generation.
- VoxCPM2: all production narration.
- Beads: durable task tracking and production blockers.

## Agent Skill Routing

Use project skills under `.agents/skills/`:

- creative direction → `creative-director`
- end-to-end video orchestration → installed `creative-video-orchestrator`
- reference analysis → `reference-deconstructor`
- factual research → `research-editor`
- script beats → `short-script-editor`
- storyboard → `storyboard-director`
- animatic → `animatic-director`
- shot method → `shot-designer`
- AI image generation → `ai-visual-producer`
- H3 video generation → `h3-video-director` through local SSH transport
- automatic local edit → installed `video-editing` skill, applied to Hajimi's `roughcut` workflow
- optional premium edit → `resolve-editor`
- sound → `sound-designer`
- shot QC → `fast-media-qc`
- master QC → `final-master-qc`
- YouTube upload → `youtube-publisher`
- analytics → `analytics-reviewer`
- idea discovery → `idea-discovery`
- idea competition → `idea-tournament`
- visual direction → `visual-concept-director`
- generation planning → `generation-director`
- voice direction → `voice-director`
- voice synthesis → local VoxCPM2 adapter (`voxcpm2_local`)

Do not silently combine unrelated roles.

## Beads

Use `bd` for durable task tracking when available. Beads is advisory and must
never block user-authorized `git status`, `git add`, `git commit`, or `git push`.
If Beads is unavailable, locked, or reports an embedded-mode limitation,
record the warning and continue the requested work. Do not modify Git hooks to
make Beads authoritative.

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
