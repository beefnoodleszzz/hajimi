# Hajimi V2

Hajimi is a small, AI-first visual storytelling studio for `The World You
Never Knew`. The active system is organized around an episode manifest, a
Shot Contract, Codex image candidates, Google Flow browser video candidates,
DaVinci Resolve/Fusion handoffs, local VoxCPM2 narration, and a five-tier Fast
QC funnel.

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

AI candidates must pass deterministic and representative-frame QC before they
enter Resolve. Generated assets and provenance under each episode's `shots/`
directory are the artifact source of truth; paths are repo-relative.

Resolve and YouTube checks are capability/readiness contracts, not hidden
automation. Use `uv run hajimi resolve doctor` and
`uv run hajimi publish doctor EP001_cloud-weight`; an external visible runtime is
required before any mutation or upload. YouTube defaults to a private upload.

Ordinary GitHub Core CI runs the Python contracts and compile checks only. Real
browser-generation and Resolve checks require their visible local sessions and
are not required for ordinary CI.

## Architecture

```text
episode.yaml
  → research / creative brief / beats / storyboard
  → animatic gate
  → shot contract / reference pack / route decision
  → one Codex image_gen keyframe when the shot benefits from image-first control
  → or native text-to-video / multi-keyframe / variation in Google Flow via ego-browser
  → local image and video candidates with provenance
  → shot QC
  → Fast QC (metadata → proxy → scenes → 3 frames → CV → contact sheet)
  → Resolve edit / Fusion / Fairlight
  → master QC
  → ego-browser YouTube Studio publish (private by default)
  → analytics
```

State is stored in `studio/studio.sqlite3` and project-level orchestration
evidence lives in `.amv/`. The database is intentionally local; Beads remains
the durable task tracker.

## Boundaries

FFmpeg is used for mechanical media operations and deterministic QC. Resolve
remains the creative editor and sound mixer. The YouTube adapter only prepares
and records a safe private preflight unless an explicitly authorized browser
session performs the upload.

Current generation boundaries are intentionally thin: `studio/generation/image.py`
prepares Codex image jobs and registers local image artifacts;
`studio/generation/video.py` prepares Google Flow browser jobs, registers local
downloads, and refuses approval without a local file. Neither module calls a
provider API or invents an SDK.
