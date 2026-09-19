# Hajimi Production Runbook

This is the operational how-to for producing one episode. Run commands from the
repository root with `EPISODE_ID` set. `episode.yaml` is the only episode state
source; `uv run hajimi readiness "$EPISODE_ID" --json` tells the orchestrator
which phase owns the next missing artifact.

## PHASE 0 — Preflight

- **Purpose:** Create an isolated episode and verify the managed skill stack.
- **Required Specialist Skills:** `creative-video-orchestrator`.
- **Hajimi Adapter:** none.
- **Inputs:** approved episode ID and local repository.
- **Output Artifacts:** `episodes/<episode>/episode.yaml` and standard directories.
- **Gate:** Skill Doctor `PASS`; duplicate skills, broken links, empty directories, and routing errors are all empty.
- **Actual CLI commands:** `uv sync`; `uv run hajimi skills doctor --json`; `uv run hajimi new "$EPISODE_ID"`; `uv run hajimi readiness "$EPISODE_ID" --json`.
- **Failure Route:** repair only the reported managed skill or manifest fault, then rerun the same check.

## PHASE 1 — Topic + Research

- **Purpose:** establish the topic promise and sourced factual basis.
- **Required Specialist Skills:** `idea-discovery`, `research-editor`, `reference-deconstructor`.
- **Hajimi Adapter:** `creative-director`.
- **Inputs:** channel strategy and approved topic.
- **Output Artifacts:** `research/topic_brief.md`, `research/fact_pack.md`, `research/reference_deconstruction.json`.
- **Gate:** factual claims have source evidence and `hajimi research` returns `PASS`.
- **Actual CLI commands:** `uv run hajimi research "$EPISODE_ID" --json`; `uv run hajimi readiness "$EPISODE_ID" --json`.
- **Failure Route:** return missing or unsupported claims to `research-editor`.

## PHASE 2 — Idea Discovery + Tournament

- **Purpose:** compare materially different audience-facing ideas before selection.
- **Required Specialist Skills:** `idea-discovery`, `idea-tournament`.
- **Hajimi Adapter:** `creative-director`.
- **Inputs:** Phase 1 research artifacts and prior channel evidence.
- **Output Artifacts:** `creative/idea_analysis.yaml`, `creative/angle_tournament.yaml`.
- **Gate:** candidates and tournament validate against the creative artifact contracts.
- **Actual CLI commands:** `uv run hajimi creative context "$EPISODE_ID" --json`; `uv run hajimi readiness "$EPISODE_ID" --json`.
- **Failure Route:** revise the owning agent artifact; Python does not choose a winner.

## PHASE 3 — Creative Direction

- **Purpose:** lock one viewer promise, emotional curve, hero shot, and ending.
- **Required Specialist Skills:** `creative-director`.
- **Hajimi Adapter:** `creative-director`.
- **Inputs:** idea analysis, tournament, and research.
- **Output Artifacts:** `creative/creative_direction.yaml`.
- **Gate:** core question, promise, opening, narrative engine, visual peaks, hero shot, ending, and rejections are explicit.
- **Actual CLI commands:** `uv run hajimi readiness "$EPISODE_ID" --json`.
- **Failure Route:** return to `creative-director`; do not change providers or runtime architecture.

## PHASE 4 — Short-form Script Craft

- **Purpose:** lock retention craft, hook competition, mute-first comprehension, and beat cadence.
- **Required Specialist Skills:** `short-form-video-script`.
- **Hajimi Adapter:** `short-script-editor`.
- **Inputs:** research, creative direction, and tournament.
- **Output Artifacts:** `creative/hook_competition.yaml`, `creative/mute_read.yaml`, `creative/beat_script.yaml`.
- **Gate:** 3–5 distinct hooks; MUTE READ `PASS`; `beat-script-v2` fields and fact references validate.
- **Actual CLI commands:** `uv run hajimi creative script-validate "$EPISODE_ID" --json`; `uv run hajimi readiness "$EPISODE_ID" --json`.
- **Failure Route:** return hook, mute read, or beats to `short-form-video-script`; `short-script-editor` only maps approved craft into Hajimi artifacts.

## PHASE 5 — Visual Concept

- **Purpose:** define visible information and meaningful visual action for every beat.
- **Required Specialist Skills:** `visual-concept-director`.
- **Hajimi Adapter:** none.
- **Inputs:** beat script and creative direction.
- **Output Artifacts:** `creative/visual_concept.yaml`.
- **Gate:** every beat has an information-bearing visual action and at least one hero frame.
- **Actual CLI commands:** `uv run hajimi creative package "$EPISODE_ID" --agent-dir /path/to/agent-output`; `uv run hajimi creative validate "$EPISODE_ID" --json`; `uv run hajimi readiness "$EPISODE_ID" --json`.
- **Failure Route:** return narration-only beats to visual concept or script craft.

## PHASE 6 — Storyboard + Continuity + Shot Contracts

- **Purpose:** turn beats into ordered shots with explicit state handoffs and one visible action each.
- **Required Specialist Skills:** `storyboard-director`, `short-drama-agent`, `shot-designer`.
- **Hajimi Adapter:** `storyboard-director`.
- **Inputs:** beat script and visual concept.
- **Output Artifacts:** `storyboard/storyboard_v01.yaml`, `storyboard/continuity_review.yaml`, `shots/Sxxx/shot.yaml`.
- **Gate:** continuity review matches all shot IDs; receive/handoff, direction, identity, environment, props, camera relation, motion, and audio bridge are explicit; H3 shots carry `audio_intent`.
- **Actual CLI commands:** `uv run hajimi readiness "$EPISODE_ID" --json`.
- **Failure Route:** route ordering and handoff faults to `storyboard-director`, and contract faults to `shot-designer`.

## PHASE 7 — Animatic + Director Review + Production Gate

- **Purpose:** prove story rhythm before paid production.
- **Required Specialist Skills:** `animatic-director`.
- **Hajimi Adapter:** `animatic-director`.
- **Inputs:** storyboard and Shot Contracts.
- **Output Artifacts:** `animatic/animatic.mp4`, `animatic/gate.json`.
- **Gate:** automation passes and director approval binds to the unchanged animatic; `production_gate == PASS`.
- **Actual CLI commands:** `uv run hajimi animatic "$EPISODE_ID" --force`; `uv run hajimi animatic-review "$EPISODE_ID" --approve --reviewer director`; `uv run hajimi readiness "$EPISODE_ID" --json`.
- **Failure Route:** return pacing faults to storyboard or script; never start production generation on a blocked gate.

## PHASE 8 — Generation Director Production Plan

- **Purpose:** decide how each approved Shot Contract will be produced.
- **Required Specialist Skills:** `generation-director`.
- **Hajimi Adapter:** none.
- **Inputs:** passed animatic, storyboard, continuity review, Shot Contracts, and `episode.yaml` timeline.
- **Output Artifacts:** `production/generation_plan.yaml` with method, budgets, input strategy, `edit_duration_sec`, and `generation_duration_sec`.
- **Gate:** plan is post-animatic; shot IDs match; edit durations match the manifest; H3 duration and input strategy validate.
- **Actual CLI commands:** `uv run hajimi production plan-record "$EPISODE_ID" --file /path/to/generation_plan.yaml`; `uv run hajimi production plan-validate "$EPISODE_ID" --json`.
- **Failure Route:** return the plan to `generation-director`; do not change Shot Contract intent to satisfy a production method.

## PHASE 9 — GPT Image Production

- **Purpose:** create and select identity-safe keyframes.
- **Required Specialist Skills:** `gpt-image-2-style-library`.
- **Hajimi Adapter:** `ai-visual-producer`.
- **Inputs:** visual concept, Shot Contract, continuity review, and selected references.
- **Output Artifacts:** `shots/Sxxx/images/prompt.md`, `prompt.json`, candidates, and `selected_keyframe.png`.
- **Gate:** style and prompt are agent-authored, hashes validate, and the director selects the keyframe.
- **Actual CLI commands:** `uv run hajimi image prompt-record "$EPISODE_ID" S001 --prompt-file /path/to/prompt.md --style-decision /path/to/style.yaml`; `uv run hajimi image prepare "$EPISODE_ID" --shot S001`; execute Codex `image_gen`; `uv run hajimi image register "$EPISODE_ID" --shot S001 --source /path/to/candidate.png --candidate 1`; `uv run hajimi image select "$EPISODE_ID" --shot S001 --candidate 1 --reviewer director`.
- **Failure Route:** revise the prompt or reference through the two named skills; never invent prompt language in Python.

## PHASE 10 — H3 Prompt Production

- **Purpose:** author the official motion and native sound expression without changing director intent.
- **Required Specialist Skills:** `generation-director`, `h3-prompt-writing`.
- **Hajimi Adapter:** `h3-video-director`.
- **Inputs:** production plan, Shot Contract, selected first/last/reference images, `audio_intent`, and durations.
- **Output Artifacts:** `shots/Sxxx/h3/prompt.txt`, `prompt.json` containing both `audio_intent` and `overall_soundscape`.
- **Gate:** official structure validates; native audio is requested; narration/dialogue/music policy is explicit; prompt hashes match.
- **Actual CLI commands:** `uv run hajimi h3 prompt-record "$EPISODE_ID" --shot S001 --prompt-file /path/to/prompt.txt`; `uv run hajimi readiness "$EPISODE_ID" --json`.
- **Failure Route:** return language to `h3-prompt-writing`; Python records and rejects but never rewrites it.

## PHASE 11 — AutoDL H3 Render

- **Purpose:** render cinematic motion and native ambience through the unchanged remote contract.
- **Required Specialist Skills:** `h3-prompt-writing`.
- **Hajimi Adapter:** `h3-video-director`.
- **Inputs:** prompt artifacts, selected reference assets, and production plan.
- **Output Artifacts:** `remote_jobs/<job>/job.json` and pulled remote candidate media/metadata.
- **Gate:** H3 Doctor passes, prompt bytes and hashes remain unchanged, and native audio metadata exists.
- **Actual CLI commands:** `uv run hajimi h3 doctor --json`; `uv run hajimi h3 prepare "$EPISODE_ID" --shot S001`; `uv run hajimi h3 submit "$EPISODE_ID" --shot S001`; `uv run hajimi h3 status "$EPISODE_ID" --shot S001`; `uv run hajimi h3 pull "$EPISODE_ID" --shot S001`.
- **Failure Route:** stop the remote batch, preserve local work, and repair prompt/reference/workflow or transport before retrying.

### Hero smoke policy

```text
PREPARE ALL LOCALLY
→ START AUTODL
→ H3 DOCTOR
→ ONE HERO CANDIDATE
→ LOCAL REVIEW
→ PASS? YES: remaining shots / NO: fix prompt, reference, or workflow first
```

The first production run must not batch the whole episode before this one-candidate HERO smoke passes.

## PHASE 12 — Candidate Review + Shot QC

- **Purpose:** select one local candidate and bind technical plus director approval to its hash.
- **Required Specialist Skills:** `fast-media-qc`.
- **Hajimi Adapter:** `h3-video-director`.
- **Inputs:** pulled candidates and sidecars.
- **Output Artifacts:** selected media, provenance, cached QC report, and director review.
- **Gate:** deterministic QC runs first; representative review passes; no unresolved artifact remains.
- **Actual CLI commands:** `uv run hajimi h3 select "$EPISODE_ID" --shot S001 --candidate 1 --reviewer director`; `uv run hajimi qc shot "$EPISODE_ID" S001`; `uv run hajimi qc review "$EPISODE_ID" S001 --decision PASS --reviewer director`.
- **Failure Route:** reject the candidate and return to the prompt/reference owner; do not approve around a failed check.

## PHASE 13 — VoxCPM2 Narration

- **Purpose:** render production narration with the locked local voice and locked script.
- **Required Specialist Skills:** `voice-director`.
- **Hajimi Adapter:** `voice-director` with `voxcpm2_local`.
- **Inputs:** beat script and `audio/voice_plan.yaml`.
- **Output Artifacts:** reviewed takes, `audio/production/narration.wav`, and `audio/voice_manifest.yaml`.
- **Gate:** provider is local VoxCPM2, voice is `science_female_main`, takes are selected, and script hash is current.
- **Actual CLI commands:** `uv run hajimi voice doctor "$EPISODE_ID" --json`; `uv run hajimi voice plan "$EPISODE_ID"`; `uv run hajimi voice render "$EPISODE_ID"`; `uv run hajimi voice review "$EPISODE_ID" B001 --select candidate_01 --reviewer director`; `uv run hajimi voice assemble "$EPISODE_ID"`; `uv run hajimi voice status "$EPISODE_ID" --json`.
- **Failure Route:** rerender or reselect through `voice-director`; never substitute cloud or temporary speech for master narration.

## PHASE 14 — Sound Design

- **Purpose:** define narration, H3 ambience, optional music/SFX, transitions, and subtitle intent.
- **Required Specialist Skills:** `sound-designer`.
- **Hajimi Adapter:** `ffmpeg-rough-editor`.
- **Inputs:** approved H3 audio, production narration, and edit intent.
- **Output Artifacts:** `edit/roughcut.yaml` with absent optional paths recorded as `null`.
- **Gate:** every configured path exists; native ambience and narration have defined roles.
- **Actual CLI commands:** `uv run hajimi readiness "$EPISODE_ID" --json`.
- **Failure Route:** return missing or conflicting cues to `sound-designer`.

## PHASE 15 — FFmpeg Edit

- **Purpose:** build the complete automatic rough master.
- **Required Specialist Skills:** `video-editing`, `sound-designer`.
- **Hajimi Adapter:** `ffmpeg-rough-editor`.
- **Inputs:** approved shots, VoxCPM2 narration, native ambience, and optional music/SFX/subtitles.
- **Output Artifacts:** `master/<episode>_rough_vNNN.mp4`, `edit/roughcut_manifest.json`; `master.source = ffmpeg`.
- **Gate:** probe and manifest hashes pass; optional music and subtitles remain optional.
- **Actual CLI commands:** `uv run hajimi roughcut build "$EPISODE_ID"`; `uv run hajimi qc episode "$EPISODE_ID" --force`.
- **Failure Route:** repair the exact media, timeline, or audio contract reported by FFmpeg/QC.

## PHASE 16 — Master QC

- **Purpose:** bind deterministic and human playback evidence to the active master hash.
- **Required Specialist Skills:** `final-master-qc`.
- **Hajimi Adapter:** none.
- **Inputs:** active FFmpeg or Resolve master, manifest, audio, subtitles, and shot QC.
- **Output Artifacts:** `qc/master_report.json` and human playback record.
- **Gate:** Master QC `PASS` on the unchanged active master plus recorded human review.
- **Actual CLI commands:** `uv run hajimi qc master "$EPISODE_ID" --force`; `uv run hajimi qc master "$EPISODE_ID" --record-human-playback --reviewer director`.
- **Failure Route:** return to the owning edit, sound, shot, or optional finish phase and rerun QC after change.

## PHASE 17 — Optional Resolve

- **Purpose:** apply premium pacing, Fusion, color, or Fairlight only when it materially improves the release.
- **Required Specialist Skills:** `resolve-editor`.
- **Hajimi Adapter:** `resolve-editor`.
- **Inputs:** release-quality FFmpeg rough master and approved premium finishing intent.
- **Output Artifacts:** Resolve handoff, export, readback, and registered `master.source = resolve`.
- **Gate:** if FFmpeg is release-quality, skip this phase; if used, Resolve readback and a fresh Master QC must pass.
- **Actual CLI commands:** `uv run hajimi resolve doctor --json`; `uv run hajimi resolve sync "$EPISODE_ID"`; `uv run hajimi resolve readback "$EPISODE_ID" --file /path/to/readback.json`; `uv run hajimi master "$EPISODE_ID" --input /path/to/resolve-export.mp4`; `uv run hajimi qc master "$EPISODE_ID" --force`.
- **Failure Route:** keep the FFmpeg master active or repair the Resolve export/readback; never make Resolve mandatory.

## PHASE 18 — YouTube Private Upload

- **Purpose:** prepare and execute a private upload only after release evidence is complete.
- **Required Specialist Skills:** `youtube-publisher`.
- **Hajimi Adapter:** `youtube-publisher`.
- **Inputs:** active master, passing Master QC, human playback, title, description, audience, and disclosure.
- **Output Artifacts:** `publish/preflight.json`, private upload, and `publish/youtube.json`.
- **Gate:** preflight `READY`; FFmpeg source needs no Resolve readback; Resolve source does.
- **Actual CLI commands:** `uv run hajimi publish doctor "$EPISODE_ID" --json`; `uv run hajimi publish youtube "$EPISODE_ID" --private --json`; after browser upload, `uv run hajimi publish record "$EPISODE_ID" --file /path/to/upload-readback.json`.
- **Failure Route:** resolve the named metadata, hash, QC, review, or readback failure; keep visibility private.

## PHASE 19 — YouTube Checks / Publish

- **Purpose:** record platform processing checks and publish only under explicit authorization.
- **Required Specialist Skills:** `youtube-publisher`.
- **Hajimi Adapter:** `youtube-publisher`.
- **Inputs:** private upload and YouTube processing/check evidence.
- **Output Artifacts:** recorded checks and final publish state.
- **Gate:** HD processing, audio, subtitles, audience, disclosure, and visibility checks pass; public/scheduled action is explicitly authorized.
- **Actual CLI commands:** `uv run hajimi publish checks "$EPISODE_ID" --file /path/to/youtube-checks.json`; `uv run hajimi publish status "$EPISODE_ID" --json`.
- **Failure Route:** retain private visibility and repair the failed platform check.

## PHASE 20 — Analytics Feedback

- **Purpose:** initialize the feedback record that informs later topic and craft decisions.
- **Required Specialist Skills:** `analytics-reviewer`.
- **Hajimi Adapter:** `analytics-reviewer`.
- **Inputs:** completed publication state and later channel metrics.
- **Output Artifacts:** episode analytics record and review findings.
- **Gate:** analytics record exists; later interpretations separate observed metrics from inference.
- **Actual CLI commands:** `uv run hajimi analytics init "$EPISODE_ID"`; `uv run hajimi readiness "$EPISODE_ID" --json`.
- **Failure Route:** keep the episode complete and retry analytics ingestion without changing production artifacts.

## Daily production model

```text
HAJIMI = Local Director / Brain
GPT-Image = Keyframe Artist
MiniMax H3 = Remote Motion + Native Ambience Renderer
VoxCPM2 = Narrator
FFmpeg = Automatic Editor
Resolve = Optional Premium Finishing Room
YouTube = Distribution
```

Prepare research, creative, script, storyboard, animatic, all keyframes, all H3
prompts, and all remote packages locally before starting AutoDL.

## Stop engineering rule

Once this flow can produce a complete episode, new providers, abstractions,
queues, databases, service splits, skills, cleanup, and future expansion belong
in the backlog. Only a demonstrated blocker in content production, image
generation, H3, sound, editing, QC, or publishing may interrupt the first real
episode.
