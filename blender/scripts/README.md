# Blender project scripts

The public entry point is `uv run hajimi blender ...`. It writes deterministic
headless runtime scripts into `blender/generated/runtime/` and keeps all
scenes, render sequences, QC, hashes, and Resolve handoff manifests under
`blender/generated/artifacts/`.

Do not run Blender final delivery as MP4. Use the generated PNG sequence in
Resolve, where edit, compositing, audio, subtitles, and export remain owned by
the editorial pipeline.
