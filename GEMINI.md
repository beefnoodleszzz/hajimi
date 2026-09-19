# Hajimi Studio

Read `AGENTS.md` and follow the production-stage routes and gates in
`config/skill-routing.yaml`. Load only canonical specialist skills and Hajimi
adapters required by the current stage.

`episodes/<episode_id>/episode.yaml` is the production source of truth. Use
local Codex `image_gen` for images, local VoxCPM2 for production narration,
AutoDL/ComfyUI/MiniMax H3 for remote video with native ambience, FFmpeg for the
complete rough master, optional Resolve for premium finishing, and local
YouTube publishing. Do not introduce another provider or skip a production
gate.
