# Hajimi V2

Hajimi is a small, AI-first visual storytelling studio for `The World You
Never Knew`. The active system is organized around an episode manifest, a
Shot Contract, local Codex image candidates, remote ComfyUI MiniMax H3 video
and native ambience, local VoxCPM2 narration, FFmpeg rough-cut assembly,
optional Resolve finishing, and a five-tier Fast QC funnel.

## Quick start

```bash
uv sync
# Optional full ASR + scene-detection QC (enables locked-script diff)
uv sync --extra media-qc
# Analytics export (DuckDB + Parquet)
uv sync --extra analytics
uv run hajimi status EP001_cloud-weight
uv run hajimi animatic EP001_cloud-weight
uv run hajimi qc episode EP001_cloud-weight
uv run hajimi master EP001_cloud-weight --input episodes/EP001_cloud-weight/master/EP001_cloud-weight_master_final.mp4
uv run hajimi qc master EP001_cloud-weight
uv run hajimi h3 doctor
uv run hajimi h3 prepare EP001_cloud-weight
uv run hajimi roughcut build EP001_cloud-weight
```

The repository contains a reproducible EP001 storyboard animatic. It is a
deliberate pre-production gate: deterministic cards and temporary sound stems
prove the story rhythm before costly AI shot generation or Resolve finishing.

Animatic approval is split into three machine-readable states:
`automation_gate`, `director_review`, and `production_gate`. Run the automation
gate first, then approve the exact unchanged asset with:

```bash
uv run hajimi animatic EP001_cloud-weight --force
uv run hajimi animatic review EP001_cloud-weight --approve --reviewer director
```

H3 candidates are locally inspected and selected; selection records `qc_pending`
and is not an approval. Run shot Fast QC and any required director review before
the candidate enters the roughcut. Generated assets and provenance under each
episode's `shots/` directory are the artifact source of truth; paths are
episode-relative.

Resolve and YouTube checks are capability/readiness contracts, not hidden
automation. Use `uv run hajimi resolve doctor` and
`uv run hajimi publish doctor EP001_cloud-weight`; an external visible runtime is
required before any mutation or upload. YouTube defaults to a private upload.

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

The shared `video-editing` skill guides automatic roughcut and delivery work;
the local H3 worker/client payload is specified in
[`docs/remote-h3-protocol.md`](docs/remote-h3-protocol.md).
