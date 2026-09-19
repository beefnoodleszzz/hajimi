---
name: ffmpeg-rough-editor
description: Route Hajimi episode artifacts through the local FFmpeg roughcut contract and verify its output.
---

# Objective

Act as Hajimi's thin roughcut adapter. Use the upstream `video-editing` skill
(`maxazure/video-editing-skill`) only as a source of relevant editing
capabilities and review guidance. Map compatible choices onto Hajimi's episode
manifest and roughcut plan, then use Hajimi's existing FFmpeg executor. The
episode manifest remains the timeline source of truth.

FFmpeg is Hajimi's automatic roughcut editor and assembly executor. DaVinci
Resolve is optional premium finishing for advanced pacing, Fusion, color, and
Fairlight work; it is not required to build the roughcut.

# Inputs

- `episodes/<episode>/episode.yaml`, including the ordered timeline and active
  shot media.
- `episodes/<episode>/animatic/gate.json` with `production_gate: PASS`.
- Locally selected, QC-approved H3 shots, with production status recorded in
  the manifest and a verified media sidecar.
- Local VoxCPM2 production narration at
  `episodes/<episode>/audio/production/narration.wav`.
- `episodes/<episode>/edit/roughcut.yaml` using schema
  `hajimi-roughcut-v1`. `music` and `subtitles` may be `null`; when either is
  configured with a path, that file must exist. SFX and exact text overlays are
  optional.

# Required Workflow

1. Read the episode manifest and roughcut plan. Keep shot order and timing in
   `episode.yaml`; do not introduce a separate timeline or replace its active
   media paths.
2. Confirm the animatic gate passed. Confirm every shot has a contiguous
   timeline slot beginning at zero (the executor allows at most 0.05 seconds
   of boundary difference), and every active H3 clip is selected, approved,
   hash-verified, and has video plus native-audio streams.
3. Probe every active video and audio input with `ffprobe`. Confirm the local
   production narration is valid and check configured plan paths stay inside
   the episode directory. Use upstream guidance only where the Hajimi plan and
   executor support it.
4. Build with the project executor:

   ```bash
   uv run hajimi roughcut build "$EPISODE_ID"
   ```

5. Inspect the reported output path and
   `episodes/<episode>/edit/roughcut_manifest.json`. Confirm the recorded
   timeline, inputs and hashes, mix settings, and media probe correspond to the
   intended episode. Confirm that raw H3 clips are trimmed to edit slots and
   picture is normalized to the output geometry and frame rate. Confirm native
   H3 ambience and VoxCPM2 narration are mixed; when configured, music ducking,
   SFX, subtitles, and exact text overlays are present. Confirm target LUFS and
   true-peak limits from the manifest, then send the rough master to
   `final-master-qc` before any upload or release.

# Hajimi Handoff

The CLI calls `studio.roughcut.build_roughcut`. It writes a new versioned file
under `episodes/<episode>/master/`, writes
`episodes/<episode>/edit/roughcut_manifest.json`, and records the FFmpeg master
path in `episode.yaml`. The executor trims selected H3 clips to their timeline
slots, normalizes and concatenates picture and audio, preserves H3 native
ambience, overlays subtitles and configured text, mixes VoxCPM2 narration,
music and optional SFX, applies music ducking and manifest loudness targets,
then checks the output streams and media properties with ffprobe.

Use `fast-media-qc` and `final-master-qc` for their respective QC decisions;
the roughcut command's output probe is not a substitute for either gate.

# Quality Gate

The roughcut is ready for master QC only when the command succeeds, the output
and manifest exist, and the recorded input hashes and timeline match the
intended approved assets. The executor's ffprobe check is a roughcut check, not
a full output-stream or decode gate; final-master QC must still pass.

# Failure Conditions

Stop if the animatic gate is missing or failed; the manifest or timeline is
invalid; any shot is not locally selected and approved; required narration or
media is missing; a configured music, subtitle, SFX, or overlay asset is
missing; an asset escapes the episode directory; FFmpeg/ffprobe is unavailable;
or the executor reports invalid output. Do not bypass a failed shot/QC or
animatic gate to produce a roughcut.

# Boundaries

- Hajimi's `episode.yaml` and `edit/roughcut.yaml` own project state and
  supported edit settings.
- This adapter does not copy upstream scripts or general-purpose workflows,
  and does not replace `studio.roughcut` or invoke another editing backend.
- Use Resolve only when optional premium finishing is needed; keep FFmpeg as
  the automatic roughcut path.
