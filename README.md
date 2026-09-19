# Hajimi V2

Hajimi is a small, AI-first visual storytelling studio for `The World You
Never Knew`. The active system is organized around an episode manifest, a
Shot Contract, local Codex image candidates, remote ComfyUI MiniMax H3 video
and native ambience, local VoxCPM2 narration, FFmpeg rough-cut assembly,
optional Resolve finishing, and a five-tier Fast QC funnel.

## Quick start

```bash
uv sync
EPISODE_ID=EP099_your-episode
uv run hajimi new "$EPISODE_ID"
uv run hajimi readiness "$EPISODE_ID"
```

Agents then follow [`docs/production-runbook.md`](docs/production-runbook.md) to
author and validate each gated artifact. The core CLI checkpoints are:

```bash
uv run hajimi research "$EPISODE_ID"
uv run hajimi creative context "$EPISODE_ID"
uv run hajimi creative package "$EPISODE_ID" --agent-dir /path/to/agent-output
uv run hajimi creative validate "$EPISODE_ID"
uv run hajimi animatic "$EPISODE_ID"
uv run hajimi animatic-review "$EPISODE_ID" --approve --reviewer director
uv run hajimi production plan-record "$EPISODE_ID" --file /path/to/generation_plan.yaml
uv run hajimi production plan-validate "$EPISODE_ID"
uv run hajimi status "$EPISODE_ID"
uv run hajimi readiness "$EPISODE_ID"
```

After episode creation, author the research, creative, storyboard, and Shot
Contract artifacts in the runbook order. The animatic is a deliberate pre-production gate: deterministic cards
and temporary sound stems prove the story rhythm before costly AI shot
generation.

Animatic approval is split into three machine-readable states:
`automation_gate`, `director_review`, and `production_gate`. Run the automation
gate first, then approve the exact unchanged asset with:

```bash
EPISODE_ID=EP099_your-episode
uv run hajimi animatic "$EPISODE_ID" --force
uv run hajimi animatic-review "$EPISODE_ID" --approve --reviewer director
```

H3 candidates are locally inspected and selected; selection records `qc_pending`
and is not an approval. Run shot Fast QC and any required director review before
the candidate enters the roughcut. Generated assets and provenance under each
episode's `shots/` directory are the artifact source of truth; paths are
episode-relative.

FFmpeg builds a complete rough master from approved shots and local audio.
Resolve is optional premium finishing; `hajimi master "$EPISODE_ID" --input
<resolve-export>` registers an export only when that path is chosen. YouTube
preflight branches on `master.source`: an FFmpeg master is gated by its roughcut
manifest and hashes, while a Resolve master also requires passing Resolve
readback. YouTube defaults to a private upload.

Stage routing and artifact gates are defined in `AGENTS.md` and
`config/skill-routing.yaml`. Run `uv run hajimi skills doctor`, `list`, and
`updates` to check the canonical shared skills, project adapters, and pinned
upstream sources.

Ordinary GitHub Core CI runs the Python contracts and compile checks only. Real
H3 rendering requires the configured AutoDL worker and is not required for
ordinary CI.

## Architecture

```text
episode.yaml
  → research / creative / script / storyboard / animatic gate
  → Shot Contracts and selected local Codex image_gen keyframes
  → REMOTE_READY H3 job packages
  → AutoDL ComfyUI + MiniMax H3 renders video and native ambience
  → local pull, candidate review, QC, and selection
  → FFmpeg complete local rough cut
  → optional Resolve premium finish
  → master QC / local YouTube publish (private by default) / analytics
```

State is stored in `studio/studio.sqlite3` and project-level orchestration
evidence lives in `.amv/`. The database is intentionally local; Beads remains
the durable task tracker.

## Boundaries

Hajimi owns creative and production decisions. Codex image_gen creates images
locally; VoxCPM2 creates production narration locally. AutoDL only runs the
versioned ComfyUI MiniMax H3 render contract through SSH. ComfyUI stays on remote
localhost. FFmpeg assembles the complete reviewable rough master. Resolve is
optional premium finishing. YouTube publish remains local and defaults to
private.

Current generation boundaries are intentionally thin:
`studio/generation/image.py` prepares Codex image jobs and registers local
image artifacts; `studio/remote/` validates, packages, submits, pulls, and
selects versioned H3 jobs/results without exposing ComfyUI publicly. The remote
worker renders and probes candidates; local Hajimi remains responsible for
review and selection.

The canonical shared `video-editing` skill supplies relevant editing craft;
the thin project `ffmpeg-rough-editor` adapter routes episode artifacts through
`studio.roughcut`. The local H3 worker/client payload is specified in
[`docs/remote-h3-protocol.md`](docs/remote-h3-protocol.md).
