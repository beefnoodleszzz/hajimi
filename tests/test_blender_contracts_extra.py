from pathlib import Path

from studio.blender_stack import _profile
from studio.config import load_yaml


ROOT = Path(__file__).resolve().parents[1]


def test_final_cycles_profile_declares_benchmark_tuning_contract() -> None:
    profiles = load_yaml(ROOT / "config" / "blender" / "render_profiles.yaml")
    profile = _profile({}, profiles, "final_cycles")

    assert profile["quality"]["max_samples_from_benchmark"] is True
    assert profile["quality"]["adaptive_sampling"] is True
    assert profile["quality"]["denoise"] is True
