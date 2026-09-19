from __future__ import annotations

import json
import re
import shlex
from pathlib import Path

from studio.cli import build_parser, main
from studio.config import dump_yaml
from studio.manifest import new_manifest, validate_shot_manifest
from studio.production import record_generation_plan, validate_generation_plan, validate_production_generation_plan
from studio.readiness import episode_readiness
from studio.storyboard import validate_continuity_review


ROOT = Path(__file__).resolve().parents[1]


def _contract(shot_id: str, role: str, previous: str | None, following: str | None) -> dict:
    return {
        "shot_id": shot_id, "role": role, "narrative_purpose": "show change",
        "information_payload": "visible state", "visual_goal": "make change visible",
        "subject": "object", "environment": "room", "composition": "center",
        "camera_height": "eye", "lens_feel": "normal", "first_frame": "start",
        "end_frame": "end", "start_state": "still", "end_state": "changed",
        "subject_motion": "moves once", "environmental_motion": "none",
        "camera_motion": "locked", "lighting": "soft", "palette": "neutral",
        "previous_shot": previous, "next_shot": following, "screen_direction": "right",
        "continuity_receive": None if previous is None else "prior state",
        "continuity_handoff": None if following is None else "changed state",
        "identity_lock": "same object", "environment_lock": "same room",
        "prop_state": "unchanged", "first_frame_requirement": "stable",
        "last_frame_requirement": None, "tail_frame_requirement": "stable",
        "preserve": ["identity"], "forbidden": ["text"], "audio_intent": "room tone",
    }


def _production_fixture(tmp_path: Path) -> Path:
    episode_id = "EP099_production-lock"
    episode = tmp_path / "episodes" / episode_id
    manifest = new_manifest(episode_id)
    manifest["creative"].update({"promise": "show a change", "hero_shot": "S001", "target_duration_sec": 3.0})
    manifest["shots"] = [
        {"id": "S001", "role": "HERO", "method": "h3_i2v", "status": "storyboard", "time_start": 0.0, "time_end": 1.4},
        {"id": "S002", "role": "STORY", "method": "fusion", "status": "storyboard", "time_start": 1.4, "time_end": 3.0},
    ]
    dump_yaml(manifest, episode / "episode.yaml")
    dump_yaml({"shots": [{"id": "S001"}, {"id": "S002"}]}, episode / "storyboard" / "storyboard_v01.yaml")
    dump_yaml({"schema_version": "continuity-review-v1", "shots": {
        "S001": {"receive": None, "action": "moves", "handoff": "changed state", "screen_direction": "right", "identity_state": "same", "environment_state": "room", "prop_state": "unchanged"},
        "S002": {"receive": "changed state", "action": "settles", "handoff": None, "screen_direction": "right", "identity_state": "same", "environment_state": "room", "prop_state": "unchanged"},
    }}, episode / "storyboard" / "continuity_review.yaml")
    for shot_id, role, method, previous, following in (("S001", "HERO", "h3_i2v", None, "S002"), ("S002", "STORY", "fusion", "S001", None)):
        output = {"asset": f"shots/{shot_id}/asset.png"}
        motion = None
        if method == "h3_i2v":
            output.update({"selected_keyframe": "shots/S001/images/selected_keyframe.png", "video_dir": "shots/S001/video", "download_target": "shots/S001/video"})
            motion = {"source_keyframe": "shots/S001/images/selected_keyframe.png"}
        value = {"id": shot_id, "version": 1, "role": role, "method": method, "intent": "show change", "camera": {}, "reference_pack": {}, "shot_contract": _contract(shot_id, role, previous, following), "output": output}
        if motion:
            value["motion_plan"] = motion
        dump_yaml(value, episode / "shots" / shot_id / "shot.yaml")
    plan = {
        "schema_version": "generation-plan-v3",
        "shots": [
            {"shot_id": "S001", "tier": "HERO", "method": "h3_i2v", "image_candidates": 1, "video_candidates": 1, "edit_duration_sec": 1.4, "generation_duration_sec": 124 / 24, "input_strategy": {"first_frame": "selected_keyframe.png"}, "fusion_graphics": []},
            {"shot_id": "S002", "tier": "STORY", "method": "fusion", "image_candidates": 0, "video_candidates": 0, "edit_duration_sec": 1.6, "generation_duration_sec": 1.6, "fusion_graphics": ["exact labels"]},
        ],
    }
    dump_yaml(plan, episode / "production" / "generation_plan.yaml")
    return episode


def test_generation_plan_is_blocked_until_animatic_pass_and_matches_current_shots(tmp_path: Path) -> None:
    episode = _production_fixture(tmp_path)
    assert any("production_gate" in error for error in validate_production_generation_plan(episode))
    gate = episode / "animatic" / "gate.json"
    gate.parent.mkdir(parents=True)
    gate.write_text(json.dumps({"production_gate": "PASS"}), encoding="utf-8")
    assert validate_production_generation_plan(episode) == []
    plan = __import__("yaml").safe_load((episode / "production" / "generation_plan.yaml").read_text())
    plan["shots"][1]["shot_id"] = "S999"
    dump_yaml(plan, episode / "production" / "generation_plan.yaml")
    assert any("shot IDs" in error for error in validate_production_generation_plan(episode))


def test_generation_duration_cannot_be_shorter_than_edit_or_h3_floor() -> None:
    shot = {"shot_id": "S001", "tier": "HERO", "method": "h3_i2v", "image_candidates": 1, "video_candidates": 1, "edit_duration_sec": 1.4, "generation_duration_sec": 1.4, "input_strategy": {"first_frame": "key.png"}, "fusion_graphics": []}
    errors = validate_generation_plan({"schema_version": "generation-plan-v3", "shots": [shot]})
    assert any("124 frames" in error for error in errors)
    shot["edit_duration_sec"] = 6.0
    assert any(">= edit_duration_sec" in error for error in validate_generation_plan({"schema_version": "generation-plan-v3", "shots": [shot]}))


def test_record_generation_plan_syncs_active_methods_without_writing_into_contract(tmp_path: Path) -> None:
    episode = _production_fixture(tmp_path)
    gate = episode / "animatic" / "gate.json"
    gate.parent.mkdir(parents=True)
    gate.write_text(json.dumps({"production_gate": "PASS"}), encoding="utf-8")
    plan = __import__("yaml").safe_load((episode / "production" / "generation_plan.yaml").read_text())
    plan["shots"][1]["method"] = "footage"
    record_generation_plan(episode, plan)
    manifest = __import__("yaml").safe_load((episode / "episode.yaml").read_text())
    shot = __import__("yaml").safe_load((episode / "shots" / "S002" / "shot.yaml").read_text())
    assert manifest["shots"][1]["method"] == "footage"
    assert shot["method"] == "footage"
    assert "method" not in shot["shot_contract"]


def test_continuity_allows_terminal_nulls_but_requires_middle_handoffs() -> None:
    review = {
        "schema_version": "continuity-review-v1",
        "shots": {
            "S001": {"receive": None, "action": "enters", "handoff": "moving right", "screen_direction": "right", "identity_state": "same subject", "environment_state": "room", "prop_state": "empty hand"},
            "S002": {"receive": "moving right", "action": "lifts key", "handoff": "key raised", "screen_direction": "right", "identity_state": "same subject", "environment_state": "room", "prop_state": "key raised"},
            "S003": {"receive": "key raised", "action": "stops", "handoff": None, "screen_direction": "right", "identity_state": "same subject", "environment_state": "room", "prop_state": "key raised"},
        },
    }
    assert validate_continuity_review(review, ["S001", "S002", "S003"]) == []
    review["shots"]["S002"]["handoff"] = None
    assert any("S002.handoff" in error for error in validate_continuity_review(review, ["S001", "S002", "S003"]))


def test_h3_shot_requires_audio_continuity_direction_and_one_visible_action() -> None:
    shot = {
        "id": "S001", "version": 1, "role": "HERO", "method": "h3_i2v",
        "intent": "show one change", "camera": {}, "reference_pack": {},
        "shot_contract": {
            "shot_id": "S001", "role": "HERO", "narrative_purpose": "hook",
            "information_payload": "object changes", "visual_goal": "show change",
            "subject": "object", "environment": "room", "composition": "center",
            "lighting": "soft", "palette": "neutral", "preserve": ["identity"],
            "forbidden": ["text"], "start_state": "still", "end_state": "moved",
            "audio_intent": "room tone", "continuity_receive": None,
            "continuity_handoff": None, "screen_direction": "right",
            "subject_motion": "moves right once",
            "camera_height": "eye", "lens_feel": "normal", "first_frame": "still",
            "end_frame": "moved", "environmental_motion": "none", "camera_motion": "locked",
            "previous_shot": None, "next_shot": None, "identity_lock": "same object",
            "environment_lock": "same room", "prop_state": "unchanged",
            "first_frame_requirement": "stable", "last_frame_requirement": None,
            "tail_frame_requirement": "stable",
        },
        "motion_plan": {"source_keyframe": "shots/S001/images/selected_keyframe.png"},
        "video_candidate_plan": {"candidates": 1},
        "output": {"selected_keyframe": "shots/S001/images/selected_keyframe.png", "video_dir": "shots/S001/video", "download_target": "shots/S001/video"},
    }
    assert validate_shot_manifest(shot) == []
    del shot["shot_contract"]["audio_intent"]
    assert any("audio_intent" in error for error in validate_shot_manifest(shot))


def test_readiness_reports_remote_offline_without_crashing_local_work(tmp_path: Path) -> None:
    episode_id = "EP099_readiness"
    manifest = new_manifest(episode_id)
    manifest["creative"].update({"promise": "pending research", "hero_shot": "S001", "target_duration_sec": 10})
    manifest["shots"] = [{"id": "S001", "role": "HERO", "method": "animatic_card", "status": "planned"}]
    dump_yaml(manifest, tmp_path / "episodes" / episode_id / "episode.yaml")
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "skill-routing.yaml").write_text((ROOT / "config" / "skill-routing.yaml").read_text(), encoding="utf-8")
    result = episode_readiness(tmp_path, episode_id, remote_doctor=lambda _root: {"status": "FAIL", "error": "OFFLINE"})
    assert result["REMOTE_H3_READY"] is False
    assert result["remote_reason"] == "OFFLINE"
    assert result["current_stage"] == "research"
    assert result["required_skills"]


def test_runbook_commands_and_skill_names_are_registered() -> None:
    runbook = (ROOT / "docs" / "production-runbook.md").read_text(encoding="utf-8")
    parser = build_parser()
    commands = re.findall(r"`uv run hajimi ([^`]+)`", runbook)
    assert commands
    for command in commands:
        parser.parse_args(shlex.split(command))
    sources = __import__("yaml").safe_load((ROOT / "config" / "skill-sources.yaml").read_text())["skills"]
    expected = {
        "creative-video-orchestrator", "idea-discovery", "research-editor",
        "reference-deconstructor", "idea-tournament", "creative-director",
        "short-form-video-script", "short-script-editor", "visual-concept-director",
        "storyboard-director", "short-drama-agent", "shot-designer",
        "animatic-director", "generation-director", "gpt-image-2-style-library",
        "ai-visual-producer", "h3-prompt-writing", "h3-video-director",
        "fast-media-qc", "voice-director", "sound-designer", "video-editing",
        "ffmpeg-rough-editor", "final-master-qc", "resolve-editor",
        "youtube-publisher", "analytics-reviewer",
    }
    assert expected <= set(sources)


def test_new_episode_can_reach_research_gate_before_full_manifest_is_ready(tmp_path: Path) -> None:
    episode_id = "EP099_first-run"
    assert main(["--root", str(tmp_path), "new", episode_id]) == 0
    research = tmp_path / "episodes" / episode_id / "research"
    (research / "topic_brief.md").write_text("topic", encoding="utf-8")
    (research / "fact_pack.md").write_text("sourced fact", encoding="utf-8")
    (research / "reference_deconstruction.json").write_text("{}\n", encoding="utf-8")
    assert main(["--root", str(tmp_path), "research", episode_id, "--json"]) == 0
