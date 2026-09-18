from pathlib import Path

from studio.blender_stack import _plugin_matrix, _portableize, _profile, _target_info
from studio.config import load_yaml


ROOT = Path(__file__).resolve().parents[1]


def test_render_profiles_match_required_portrait_matrix():
    profiles = load_yaml(ROOT / "config" / "blender" / "render_profiles.yaml")
    expected = {
        "P0": ([270, 480], 15),
        "P1": ([540, 960], 30),
        "P2": ([720, 1280], 30),
        "P3": ([1080, 1920], 30),
    }
    for name, (resolution, fps) in expected.items():
        profile = _profile({}, profiles, name)
        assert profile["resolution"] == resolution
        assert profile["fps"] == fps
        assert profile["width"] == resolution[0]
        assert profile["height"] == resolution[1]


def test_validation_target_is_explicit_and_rightward():
    info = _target_info(ROOT, "EP001_TEST_01")
    assert info["kind"] == "validation_shot"
    assert info["width"] == 1080
    assert info["height"] == 1920
    assert info["screen_direction"] == "RIGHT"
    assert info["ground_lock"] is True


def test_hero_exr_profile_is_half_float_sequence_with_composite_passes():
    profiles = load_yaml(ROOT / "config" / "blender" / "render_profiles.yaml")
    profile = _profile({}, profiles, "hero_exr")
    assert profile["format"] == "OPEN_EXR"
    assert profile["color_depth"] == 16
    assert profile["color_mode"] == "RGBA"
    assert "Vector" in profile["passes"]


def test_episode_shortcut_resolves_shot_without_mutating_manifest():
    info = _target_info(ROOT, "EP001", "S005")
    assert info["episode_id"] == "EP001_earth-stop"
    assert info["shot_id"] == "S005"
    assert info["engine"] == "EEVEE"


def test_plugin_matrix_requires_a_loaded_smoke_probe_not_just_a_module_directory():
    config = load_yaml(ROOT / "config" / "blender.yaml")
    packages = {key: [] for key in config["plugins"]}
    packages["poliigon"] = ["blender/installers/poliigon-addon-blender-1.16.3.zip"]
    available_only = {"addons": {"poliigon-addon-blender": {"module": "poliigon-addon-blender", "available": True}}}
    matrix = _plugin_matrix(config, {}, packages, available_only)
    assert matrix["poliigon"]["status"] == "AVAILABLE_LOCAL_PACKAGE"
    loaded = {"addons": {"poliigon-addon-blender": {"module": "poliigon-addon-blender", "loaded": True, "enabled": True, "version": [1, 16, 3]}}}
    matrix = _plugin_matrix(config, {}, packages, loaded)
    assert matrix["poliigon"]["status"] == "PASS"
    assert matrix["poliigon"]["detected_version"] == [1, 16, 3]


def test_free_replacement_matrix_records_loaded_extension_and_replacement_role():
    config = load_yaml(ROOT / "config" / "blender.yaml")
    packages = {key: [] for key in config["plugins"]}
    packages["scatter_objects"] = ["blender/installers/scatter-objects-0.2.0.zip"]
    loaded = {
        "addons": {
            "bl_ext.user_default.scatter_objects": {
                "module": "bl_ext.user_default.scatter_objects",
                "loaded": True,
                "enabled": True,
                "version": [0, 2, 0],
            }
        }
    }
    matrix = _plugin_matrix(config, {}, packages, loaded)
    assert matrix["scatter_objects"]["status"] == "PASS"
    assert matrix["scatter_objects"]["replacement_for"] == "geoscatter"
    assert matrix["scatter_objects"]["detected_version"] == [0, 2, 0]


def test_demo_plugin_is_not_reported_as_full_production_capability():
    config = load_yaml(ROOT / "config" / "blender.yaml")
    packages = {key: [] for key in config["plugins"]}
    packages["flip_fluids"] = ["blender/installers/FLIP_Fluids_demo_release.zip"]
    loaded = {
        "addons": {
            "flip_fluids_addon": {
                "module": "flip_fluids_addon",
                "loaded": True,
                "enabled": True,
                "version": [1, 8, 8],
            }
        }
    }

    matrix = _plugin_matrix(config, {}, packages, loaded)

    assert matrix["flip_fluids"]["status"] == "DEMO_LIMITED"
    assert matrix["flip_fluids"]["capability_status"] == "DEMO_LIMITED"
    assert matrix["flip_fluids"]["production_final_allowed"] is False


def test_generated_blender_evidence_uses_portable_paths():
    payload = _portableize(
        ROOT,
        {
            "scene": str(ROOT / "blender" / "generated" / "scene.blend"),
            "assets": str(ROOT / "blender" / "assets" / "curated"),
        },
    )

    assert payload["scene"] == "./blender/generated/scene.blend"
    assert payload["assets"] == "${HAJIMI_ASSETS}/curated"
