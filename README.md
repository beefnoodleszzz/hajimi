# Hajimi V2

Hajimi is a small, AI-driven visual storytelling studio for `The World You
Never Knew`. The active system is organized around an episode manifest,
deterministic scientific visuals, DaVinci Resolve integration boundaries, and a
five-tier Fast QC funnel.

## Quick start

```bash
uv sync
# Optional full ASR + scene-detection QC (enables locked-script diff)
uv sync --extra media-qc
# Analytics export (DuckDB + Parquet)
uv sync --extra analytics
uv run hajimi status EP001_earth-stop
uv run hajimi animatic EP001_earth-stop
uv run hajimi qc episode EP001_earth-stop
uv run hajimi master EP001_earth-stop --input episodes/EP001_earth-stop/master/EP001_earth-stop_master_final.mp4
uv run hajimi qc master EP001_earth-stop
```

Blender stack verification and the deterministic validation shot:

```bash
uv run hajimi blender doctor
uv run hajimi blender bootstrap
uv run hajimi blender configure_gpu
uv run hajimi blender configure_assets
uv run hajimi blender configure_render
uv run hajimi blender benchmark
uv run hajimi blender build EP001_TEST_01 --force
uv run hajimi blender preview EP001_TEST_01 --profile P1
uv run hajimi blender render EP001_TEST_01 --profile P3
uv run hajimi blender qc EP001_TEST_01 --profile P3
uv run hajimi blender qc EP001_TEST_01 --profile P3 --deep
```

Blender final output is a PNG image sequence plus a Resolve handoff manifest;
Blender does not author the final MP4. The production baseline is Blender
`5.2.2 LTS`, installed at `/Applications/Blender.app` and exposed through the
`blender` command. The project-local stack has validated Poliigon `1.16.3`,
engon `1.10.0`, and the official FLIP Fluids `1.8.8` Demo. Photographer 5,
Geo-Scatter `5.6.4`, and Physical Atmosphere² remain correctly marked
`BLOCKED_LICENSE_PACKAGE` until their licensed ZIP packages are supplied.

The repository contains a reproducible EP001 storyboard animatic. It is a
deliberate pre-production gate: deterministic cards and temporary sound stems
prove the story rhythm before costly AI shot generation or Resolve finishing.

Animatic approval is split into three machine-readable states:
`automation_gate`, `director_review`, and `production_gate`. Run the automation
gate first, then approve the exact unchanged asset with:

```bash
uv run hajimi animatic EP001_earth-stop --force
uv run hajimi animatic review EP001_earth-stop --approve --reviewer director
```

Blender QC defaults to `FAST`: sequence continuity plus representative frame
decode. Use `--deep` only when full-sequence integrity is explicitly required.
Generated Blender/runtime evidence under `config/generated/` is local machine
evidence and is not the repository source of truth; portable asset indexes use
repo-relative paths or `${HAJIMI_ASSETS}`.

Resolve and YouTube checks are capability/readiness contracts, not hidden
automation. Use `uv run hajimi resolve doctor` and
`uv run hajimi publish doctor EP001_earth-stop`; an external visible runtime is
required before any mutation or upload. YouTube defaults to a private upload.

Ordinary GitHub Core CI runs the Python contracts and compile checks only. A
real Blender integration check belongs on an explicitly configured local or
self-hosted macOS runner and is not required for ordinary CI.

## Architecture

```text
episode.yaml
  → research / creative brief / beats / storyboard
  → animatic gate
  → shot production (Blender | AI | Fusion | footage)
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
