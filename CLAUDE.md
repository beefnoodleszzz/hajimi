# Hajimi

Read `AGENTS.md` first.

Load the relevant project skill from `.agents/skills/` before performing a
production role.

Key commands:

```bash
uv sync
EPISODE_ID=<episode_id>
uv run hajimi status "$EPISODE_ID"
uv run hajimi animatic "$EPISODE_ID"
uv run hajimi qc episode "$EPISODE_ID"
uv run hajimi qc master "$EPISODE_ID"
uv run hajimi resolve doctor
uv run hajimi publish doctor "$EPISODE_ID"
uv run hajimi creative package "$EPISODE_ID"
uv run hajimi voice doctor "$EPISODE_ID"
uv run hajimi voice plan "$EPISODE_ID"
uv run hajimi voice render "$EPISODE_ID"
uv run hajimi voice status "$EPISODE_ID"
uv run hajimi skills doctor
bd ready
```

`episode.yaml` is the single source of truth. Do not create legacy `v05` or
`v06` folders, run full-frame LLM/VLM QC, or publish a YouTube video as Public
without explicit authorization. Production narration uses the local VoxCPM2
adapter with `science_female_main` by default; temporary animatic voice is not
accepted by the master or publish pipeline. Beads records work but never
blocks authorized Git operations.

Production stage routing and required skill handoffs are defined once in
`AGENTS.md` and `config/skill-routing.yaml`; read those before production work.
FFmpeg builds the complete rough master. Resolve finishing is optional, and
`hajimi master` registers a Resolve export only when that path is used.
