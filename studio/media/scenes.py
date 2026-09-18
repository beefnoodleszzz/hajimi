"""Optional PySceneDetect integration with a safe deterministic fallback."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .probe import duration_seconds, probe_media


def detect_scenes(path: str | Path) -> tuple[list[dict[str, Any]], list[str]]:
    path = Path(path)
    warnings: list[str] = []
    try:
        from scenedetect import SceneManager, open_video  # type: ignore
        from scenedetect.detectors import AdaptiveDetector  # type: ignore

        video = open_video(str(path))
        manager = SceneManager()
        manager.add_detector(AdaptiveDetector())
        manager.detect_scenes(video=video)
        scene_list = manager.get_scene_list()
        if scene_list:
            return [
                {"start": scene[0].get_seconds(), "end": scene[1].get_seconds(), "method": "AdaptiveDetector"}
                for scene in scene_list
            ], warnings
        warnings.append("PySceneDetect returned no cuts; using one scene")
    except Exception as exc:
        warnings.append(f"PySceneDetect unavailable or failed: {exc.__class__.__name__}")
    probe = probe_media(path)
    duration = duration_seconds(probe)
    return [{"start": 0.0, "end": duration, "method": "fallback_single_scene"}], warnings
