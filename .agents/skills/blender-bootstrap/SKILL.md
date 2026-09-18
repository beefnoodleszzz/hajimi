---
name: blender-bootstrap
description: Configure and verify Hajimi's local Blender production environment without upgrading Blender, downloading assets, or installing unlicensed commercial plugins.
---

---
name: blender-bootstrap
description: Configure and verify Hajimi's local Blender production environment without upgrading Blender, downloading assets, or installing unlicensed commercial plugins.
triggers:
  - Blender bootstrap
  - Blender doctor
  - Blender configuration
  - asset browser setup
---

# Objective

Install, configure, and verify the project-local Blender production stack. This
skill configures the environment; it does not invent or author creative shots.

# Inputs

- `config/blender.yaml`
- the project-local `blender/` directories and legal installer packages
- the installed Blender binary
- the target platform and hardware

# Outputs

- `config/generated/blender_doctor.json`
- `config/generated/hardware.json`
- `config/generated/plugin_matrix.json`
- `config/generated/asset_library_matrix.json`
- `config/generated/benchmark.json`
- project-local templates, cache, runtime logs, and render artifacts

# Required Workflow

1. Detect the actual Blender binary and exact version.
2. Treat Blender 5.2.2 as the required baseline; report a mismatch as
   `BLOCKED_VERSION_MISMATCH`.
3. Use headless `bpy` evidence for Python, Eevee, Cycles, and the
   platform-appropriate GPU backend.
4. Prefer Metal on Apple Silicon, OptiX then CUDA on NVIDIA, HIP on AMD, and
   oneAPI on Intel; CPU is fallback only.
5. Register only the five project-local Asset Browser libraries: Hajimi
   Curated, Cameras, Materials, Environments, and FX.
6. Run `doctor → bootstrap → benchmark → EP001_TEST_01 build/preview/QC/render`.

# Quality Gate

The core stack is PASS only when `bpy`, Eevee, Cycles, headless execution,
asset-library paths, and project-local writable cache paths are evidenced. A
commercial plugin may be `BLOCKED_LICENSE_PACKAGE` without blocking the core
pipeline, but it must never be reported as installed or smoke-tested.

# Failure Conditions

- Blender is missing or not 5.2.2.
- Any core headless renderer smoke test fails.
- Asset libraries resolve outside the project policy without an explicit
  configuration.
- A plugin is marked PASS from a directory/package check without a loaded
  smoke probe.
- A render is attempted before preflight passes.

# Tools

`uv run hajimi blender doctor`, `bootstrap`, `configure_gpu`,
`configure_assets`, `configure_render`, `benchmark`, and the headless Blender
runtime invoked by `studio.blender_stack`.

# Forbidden Patterns

- Do not upgrade Blender automatically.
- Do not download assets or plugins during bootstrap.
- Do not buy, crack, or bypass commercial licenses.
- Do not write credentials, cookies, or tokens to Blender preferences or the
  repository.
- Do not use Blender as the final MP4 editor, subtitle renderer, or sound mixer.

# Handoff

Pass doctor, hardware, plugin, asset-library, benchmark, and validation-shot
evidence to `blender-production`. Report remaining blocked dependencies by
their exact status and path.
