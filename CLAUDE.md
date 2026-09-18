# Hajimi

Read `AGENTS.md` first.

Load the relevant project skill from `.agents/skills/` before performing a
production role.

Key commands:

```bash
uv sync
uv run hajimi status EP001_earth-stop
uv run hajimi animatic EP001_earth-stop
uv run hajimi qc episode EP001_earth-stop
uv run hajimi qc master EP001_earth-stop
uv run hajimi resolve doctor
uv run hajimi publish doctor EP001_earth-stop
uv run hajimi creative package EP001_earth-stop --force
uv run hajimi voice doctor EP001_earth-stop
uv run hajimi voice plan EP001_earth-stop
uv run hajimi voice render EP001_earth-stop
uv run hajimi voice status EP001_earth-stop
bd ready
```

`episode.yaml` is the single source of truth. Do not create legacy `v05` or
`v06` folders, run full-frame LLM/VLM QC, or publish a YouTube video as Public
without explicit authorization. Production narration uses the local VoxCPM2
adapter with `science_female_main` by default; temporary animatic voice is not
accepted by the master or publish pipeline. Beads records work but never
blocks authorized Git operations.
