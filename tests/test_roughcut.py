from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from studio.config import dump_yaml, write_json
from studio.media.hashing import sha256_file
from studio.roughcut import _overlay_position, build_roughcut


def _ffmpeg(command: list[str]) -> None:
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode:
        pytest.skip("local FFmpeg is missing a filter or codec required by the roughcut contract")


def test_overlay_position_accepts_default_center_and_rejects_expression_injection() -> None:
    assert _overlay_position("(w-text_w)/2", "x") == "(w-text_w)/2"
    with pytest.raises(ValueError):
        _overlay_position("0;movie=secret.mp4", "x")


@pytest.mark.parametrize("with_optional_assets", [False, True])
def test_build_roughcut_from_approved_h3_clip_and_local_audio(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, with_optional_assets: bool) -> None:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        pytest.skip("ffmpeg and ffprobe are required for the roughcut integration check")
    monkeypatch.setattr("studio.roughcut.production_voice_check", lambda _episode: {"pass": True, "reason": "test voice"})
    episode_id = "EP098_roughcut-test"
    episode = tmp_path / "episodes" / episode_id
    selected = episode / "shots" / "S001" / "video" / "selected.mp4"
    selected.parent.mkdir(parents=True)
    _ffmpeg([
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "color=c=navy:s=180x320:r=24:d=5.166667",
        "-f", "lavfi", "-i", "sine=frequency=330:sample_rate=48000:duration=5.166667",
        "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-t", "5.166667", str(selected),
    ])
    selected_hash = sha256_file(selected)
    write_json({"backend": "comfyui_minimax_h3", "sha256": selected_hash}, selected.with_suffix(".json"))
    voice = episode / "audio" / "production" / "narration.wav"
    voice.parent.mkdir(parents=True)
    audio_files = [(voice, "440")]
    if with_optional_assets:
        audio_files.append((episode / "audio" / "production" / "music.wav", "110"))
    for path, frequency in audio_files:
        _ffmpeg([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"sine=frequency={frequency}:sample_rate=48000:duration=1", "-c:a", "pcm_s16le", str(path)])
    music_config = "audio/production/music.wav" if with_optional_assets else None
    subtitle_config = None
    if with_optional_assets:
        captions = episode / "script" / "captions_v01.srt"
        captions.parent.mkdir()
        captions.write_text("1\n00:00:00,000 --> 00:00:00,800\nA cloud can weigh hundreds of tons.\n", encoding="utf-8")
        subtitle_config = "script/captions_v01.srt"
    dump_yaml({
        "schema_version": "hajimi-roughcut-v1",
        "music": music_config,
        "subtitles": subtitle_config,
        "music_gain_db": -18,
        "overlays": [{"text": "TEST LABEL", "start_sec": 0.1, "end_sec": 0.8, "font_size": 24}],
        "sfx": [],
    }, episode / "edit" / "roughcut.yaml")
    dump_yaml({
        "episode_id": episode_id,
        "status": "production",
        "channel": "Test",
        "format": "youtube_short",
        "language": "en-US",
        "aspect_ratio": "9:16",
        "master": {"width": 180, "height": 320, "fps": 24, "sample_rate": 48000, "source": None, "path": None},
        "creative": {"promise": "A cloud is heavy but still floats.", "hero_shot": "S001", "target_duration_sec": 1.4},
        "script": {"path": "script/script_v01.md"},
        "audio": {"narrator": "science_female_main", "target_lufs": -14, "true_peak_max_db": -1},
        "shots": [{
            "id": "S001", "role": "HERO", "method": "h3_i2v", "status": "approved",
            "active_media": "shots/S001/video/selected.mp4", "remote_status": "SELECTED",
            "time_start": 0.0, "time_end": 1.4, "duration_target": 1.4,
        }],
        "publish": {"visibility": "private"},
    }, episode / "episode.yaml")
    gate = episode / "animatic" / "gate.json"
    gate.parent.mkdir(parents=True)
    write_json({"production_gate": "PASS"}, gate)

    output = build_roughcut(episode)

    assert output.is_file() and output.stat().st_size > 0
    probe = subprocess.run([ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(output)], capture_output=True, text=True, check=True)
    streams = json.loads(probe.stdout)["streams"]
    assert any(stream["codec_type"] == "video" for stream in streams)
    assert any(stream["codec_type"] == "audio" for stream in streams)
    report = json.loads((episode / "edit" / "roughcut_manifest.json").read_text(encoding="utf-8"))
    assert report["source"] == "ffmpeg"
    assert report["timeline"][0]["shot_id"] == "S001"
    assert report["timeline"][0]["duration_sec"] == pytest.approx(1.4)
    assert report["inputs"]["music"] is None if not with_optional_assets else report["inputs"]["music"] is not None
    assert report["inputs"]["subtitles"] is None if not with_optional_assets else report["inputs"]["subtitles"] is not None
    assert float(probe.stdout and json.loads(probe.stdout)["format"]["duration"]) == pytest.approx(1.4, abs=0.08)
