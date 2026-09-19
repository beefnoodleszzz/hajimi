from __future__ import annotations

from pathlib import Path

import pytest

from studio.config import dump_yaml
from studio.remote.prompt import load_h3_prompt_artifact, validate_h3_prompt, write_h3_prompt_artifact


AUDIO_INTENT = "Soft wind moves around the platform, ending with one small scale click."
I2VA_PROMPT = """For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.

integrated_multimodal_description: [Shot 1] Grounded live-action macro imagery begins exactly from <Picture 1>. The cloud completes its gentle landing inside the first 1.2 seconds and then holds a natural stable after-motion through the remaining 5.17-second generation. No narration and no dialogue.

overall_soundscape: Soft wind moves around the platform, ending with one small scale click.

non_diegetic_music: N/A
"""


def test_base_h3_prompt_uses_official_sections_audio_and_image_alignment() -> None:
    assert validate_h3_prompt("i2va", I2VA_PROMPT, AUDIO_INTENT, 124 / 24) == []
    wrong_audio = validate_h3_prompt("i2va", I2VA_PROMPT, "heavy rain", 124 / 24)
    assert any("exactly match" in error for error in wrong_audio)
    wrong_music = I2VA_PROMPT.replace("non_diegetic_music: N/A", "non_diegetic_music: strings")
    assert any("must be N/A" in error for error in validate_h3_prompt("i2va", wrong_music, AUDIO_INTENT, 124 / 24))
    wrong_alignment = I2VA_PROMPT.replace("0.00 seconds", "0.10 seconds", 1)
    assert any("first-frame alignment" in error for error in validate_h3_prompt("i2va", wrong_alignment, AUDIO_INTENT, 124 / 24))


def test_fl2va_alignment_uses_generation_duration_and_ref2va_has_own_contract() -> None:
    fl2va = """How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot 1) aligns with the 5.17-second mark of the target video.

integrated_multimodal_description: [Shot 1] A continuous motion reaches the final reference state. No narration and no dialogue.

overall_soundscape: Soft wind moves around the platform, ending with one small scale click.

non_diegetic_music: N/A
"""
    assert validate_h3_prompt("fl2va", fl2va, AUDIO_INTENT, 124 / 24) == []
    wrong_duration = fl2va.replace("5.17-second mark", "1.40-second mark")
    assert any("generation duration" in error for error in validate_h3_prompt("fl2va", wrong_duration, AUDIO_INTENT, 124 / 24))

    ref2va = """subject_definitions: <Picture 1> is the selected opening keyframe showing the compact cloud and platform.

summary: [reference generation] Use only the supplied picture to preserve the cloud and platform identity.

retention_analysis: <Picture 1> anchors the first frame and the stable subject identity.

detailed_description: [Shot 1] The cloud settles once, then remains stable. No narration and no dialogue.

overall_soundscape: Soft wind moves around the platform, ending with one small scale click.

non_diegetic_music: N/A
"""
    assert validate_h3_prompt("ref2va", ref2va, AUDIO_INTENT, 124 / 24, reference_image_count=1) == []
    assert any("official order" in error for error in validate_h3_prompt("ref2va", I2VA_PROMPT, AUDIO_INTENT, 124 / 24, reference_image_count=1))


def test_h3_prompt_artifact_is_required_hash_bound_and_kept_unchanged(tmp_path: Path) -> None:
    shot_dir = tmp_path / "shots" / "S001"
    shot_dir.mkdir(parents=True)
    dump_yaml({"id": "S001", "shot_contract": {"audio_intent": AUDIO_INTENT}}, shot_dir / "shot.yaml")
    image_path = shot_dir / "images" / "selected_keyframe.png"
    image_path.parent.mkdir()
    image_path.write_bytes(b"selected keyframe")
    with pytest.raises(FileNotFoundError, match="H3 prompt artifact is required"):
        load_h3_prompt_artifact(tmp_path, "S001", "i2va", [image_path], 124 / 24)

    artifact = write_h3_prompt_artifact(
        tmp_path,
        "S001",
        "i2va",
        I2VA_PROMPT,
        AUDIO_INTENT,
        [image_path],
        124 / 24,
        job_revision=2,
    )
    assert artifact["job_revision"] == 2
    assert artifact["source_shot_contract_sha256"]
    assert artifact["source_keyframe_hashes"]["shots/S001/images/selected_keyframe.png"]
    assert artifact["official_skill"]["commit"] == "d21241f0a4b3acbb34c97dae47fa417b7065e438"
    loaded = load_h3_prompt_artifact(tmp_path, "S001", "i2va", [image_path], 124 / 24)
    assert loaded["prompt"] == (shot_dir / "h3" / "prompt.txt").read_text(encoding="utf-8") == I2VA_PROMPT
