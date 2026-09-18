from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_blender_specified_script_entrypoints_exist() -> None:
    required = [
        ROOT / "blender/scripts/doctor.py",
        ROOT / "blender/scripts/configure_gpu.py",
        ROOT / "blender/scripts/configure_assets.py",
        ROOT / "blender/scripts/configure_render.py",
        ROOT / "blender/scripts/benchmark.py",
        ROOT / "blender/scripts/render_shot.py",
        ROOT / "blender/scripts/startup/hajimi_bootstrap.py",
    ]
    assert all(path.exists() for path in required)
