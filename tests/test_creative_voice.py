from __future__ import annotations

from pathlib import Path

from studio.config import dump_yaml, load_yaml
from studio.creative import discover_ideas, generate_creative_package, run_tournament, validate_creative_package, validate_generation_plan
from studio.voice.manifest import VOICE_PROVIDER, production_voice_check, script_hash, write_voice_manifest
from studio.voice.voxcpm2 import _source_payload, review_voice, route_emotion, select_voice


def _manifest(episode_id: str) -> dict:
    return {
        "episode_id": episode_id,
        "status": "creative_brief",
        "channel": "Test Channel",
        "format": "youtube_short",
        "language": "en",
        "aspect_ratio": "9:16",
        "master": {"width": 1080, "height": 1920, "fps": 30, "sample_rate": 48000},
        "creative": {"topic": "A new topic", "target_duration_sec": 20},
        "script": {"path": "creative/beat_script.yaml"},
        "audio": {"narrator": None, "target_lufs": -14, "true_peak_max_db": -1},
        "shots": [{"id": "S001", "role": "hero", "method": "ai_image", "status": "planned"}],
        "publish": {"visibility": "private"},
    }


def _agent_outputs() -> dict[str, dict]:
    candidate = {
        "id": "dynamic_candidate",
        "title_working": "The delayed consequence",
        "premise": "A familiar system reveals a hidden delay.",
        "viewer_question": "Why does the result arrive later?",
        "surprising_fact": "The visible result is not simultaneous with the cause.",
        "emotional_driver": "curiosity",
        "hook_potential": {"first_second_event": "The result appears before the cause.", "first_visual": "A split-time object", "contradiction": "Cause and effect are reversed", "curiosity_gap": "What is lagging?"},
        "visual_potential": {"opening_visual": "Split-time object", "escalation_visuals": ["layers drift apart"], "hero_visual": "All layers separated", "ending_visual": "layers reunite"},
        "story_potential": {"setup": "show the anomaly", "escalation": "reveal hidden layers", "payoff": "explain the delay", "loop": "return to opening"},
        "production_fit": {"h3_i2v": "possible", "h3_fl2v": "possible", "ai_image": "possible", "fusion": "possible", "footage": "unlikely"},
        "novelty": {"common_existing_angle": "generic explanation", "alternative_angle": "time-layer reveal", "distinctive_angle": "visible causal lag"},
        "risk": {"factual": "needs research", "visual": "continuity", "generation": "layer drift"},
        "evidence": {"source_refs": [], "reference_patterns": []},
    }
    return {
        "idea_analysis.yaml": {"schema_version": "idea-analysis-v2", "candidates": [candidate]},
        "angle_tournament.yaml": {
            "schema_version": "angle-tournament-v2",
            "angle_mutations": [{"id": "m1", "source_candidate": "dynamic_candidate", "angle": "visual-first", "premise": "Show the lag before explaining it."}],
            "comparisons": [{"left": "dynamic_candidate", "right": "m1", "stronger": "m1", "reasoning": "The anomaly is immediate.", "dimensions": {"hook": 5, "visual": 5, "escalation": 4, "originality": 4, "production_fit": 4}}],
            "selected_direction": {"hook_from": "m1", "visual_motif_from": "m1", "escalation_from": "m1", "payoff_from": "dynamic_candidate", "ending_from": "m1", "rationale": "Composite direction keeps the immediate anomaly and clear explanation."},
        },
        "creative_direction.yaml": {"core_question": "Why is the result delayed?", "one_sentence_promise": "You will see the hidden delay before you learn its cause.", "opening": "Show the result arriving first.", "narrative_engine": "anomaly to layered explanation", "visual_peaks": ["layer separation"], "hero_shot": "S001", "ending": "return to the first image with new meaning", "reject": ["generic lecture"]},
        "visual_concept.yaml": {"visual_language": {"motif": "misaligned time layers"}, "hero_frames": ["S001"], "shots": [{"shot_id": "S001", "tier": "HERO", "visual_goal": "make causal lag visible", "composition": "centered split frame", "focal_subject": "layered object", "camera": "slow push", "action": "layers separate", "transition": "match back to opening", "method_candidates": ["ai_image", "h3_i2v"]}], "rejections": ["talking head"]},
        "beat_script.yaml": {"schema_version": "beat-script-v2", "duration_sec": 5, "beats": [{"id": "B001", "purpose": "hook", "narration": "The result arrives before the cause.", "visual_action": "result appears", "visual_information": "cause is absent", "camera_event": "snap push", "sound_event": "short impact", "emotional_change": "surprise", "duration_target": 5}]},
        "generation_plan.yaml": {"schema_version": "generation-plan-v3", "shots": [{"shot_id": "S001", "tier": "HERO", "method": "hybrid_ai", "image_candidates": 1, "video_candidates": 2, "fusion_graphics": [], "forbidden": ["unmotivated text overlay"]}]},
    }


def test_ep002_uses_dynamic_agent_outputs_without_python_seed(tmp_path: Path) -> None:
    episode_id = "EP002_new-topic"
    episode_root = tmp_path / "episodes" / episode_id
    dump_yaml(_manifest(episode_id), episode_root / "episode.yaml")

    result = generate_creative_package(tmp_path, episode_id, force=True, agent_outputs=_agent_outputs())

    assert result["status"] == "PASS"
    assert not validate_creative_package(episode_root / "creative")
    assert result["hero_shot"] == "S001"
    source = Path("studio/creative.py").read_text()
    assert "_ep001_ideas" not in source
    assert "rank = {" not in source


def test_missing_agent_outputs_blocks_instead_of_inventing_answer(tmp_path: Path) -> None:
    episode_id = "EP002_new-topic"
    episode_root = tmp_path / "episodes" / episode_id
    dump_yaml(_manifest(episode_id), episode_root / "episode.yaml")

    result = generate_creative_package(tmp_path, episode_id, force=True)

    assert result["status"] == "BLOCKED_AGENT_INPUT"
    assert result["missing"]
    assert not (episode_root / "creative" / "idea_analysis.yaml").exists()
    assert discover_ideas({"episode": {"id": episode_id}})["status"] == "AGENT_INPUT_REQUIRED"
    assert run_tournament({"candidates": []})["status"] == "AGENT_INPUT_REQUIRED"


def test_generation_plan_candidate_requirements_follow_method() -> None:
    base = {"shot_id": "S001", "tier": "STORY", "fusion_graphics": [], "forbidden": ["fake text"]}
    fusion = {**base, "method": "fusion"}
    t2v = {**base, "method": "h3_ref2v", "image_candidates": 1, "video_candidates": 1}
    i2v = {**base, "method": "h3_i2v", "image_candidates": 1, "video_candidates": 1}
    assert validate_generation_plan({"shots": [fusion, t2v, i2v]}) == []


def test_voice_source_carries_per_beat_controls_and_candidates(tmp_path: Path) -> None:
    episode_id = "EP002_new-topic"
    episode_root = tmp_path / "episodes" / episode_id
    dump_yaml(_manifest(episode_id), episode_root / "episode.yaml")
    dump_yaml({"beats": [{"id": "B001", "narration": "Look.", "purpose": "hook"}, {"id": "B002", "narration": "Now explain.", "purpose": "explanation"}]}, episode_root / "creative" / "beat_script.yaml")
    dump_yaml({"narrator": "real_voice", "voice_direction": {"beats": [{"id": "B001", "voxcpm2": {"emotion": "panic", "style": "neutral", "mode": "controllable", "instruct": "urgent", "candidate_count": 3}}, {"id": "B002", "voxcpm2": {"emotion": "neutral", "style": "neutral", "mode": "controllable", "instruct": "calm", "candidate_count": 1}}]}}, episode_root / "audio" / "voice_manifest.yaml")

    source = _source_payload(tmp_path, episode_id)

    assert [(line["id"], line["mode"], line["instruct"], line["candidates"]) for line in source["lines"]] == [("B001", "controllable", "urgent", 3), ("B002", "controllable", "calm", 1)]


def test_voice_director_maps_real_english_intents_to_voxcpm2_routes(monkeypatch, tmp_path: Path) -> None:
    project = tmp_path / "voxcpm2"
    (project / "src").mkdir(parents=True)
    (project / "src" / "emotions.py").write_text(
        "ROUTES = {'neutral': 'neutral', 'gentle': 'gentle', 'angry': 'angry', 'sad': 'sad'}\n"
        "INSTRUCTIONS = {'neutral': 'neutral', 'gentle': 'gentle', 'angry': 'angry', 'sad': 'sad'}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("VOXCPM_PROJECT", str(project))

    assert route_emotion("curiosity to danger") == "angry"
    assert route_emotion("systemic dread") == "angry"
    assert route_emotion("awe") == "gentle"


def test_voice_review_selects_candidates_per_beat(tmp_path: Path) -> None:
    episode_id = "EP002_new-topic"
    episode_root = tmp_path / "episodes" / episode_id
    dump_yaml(_manifest(episode_id), episode_root / "episode.yaml")
    dump_yaml({"takes": {"B001": {"candidates": [{"id": "candidate_01"}, {"id": "candidate_03"}]}, "B002": {"candidates": [{"id": "candidate_01"}, {"id": "candidate_02"}]} }}, episode_root / "audio" / "voice_manifest.yaml")

    first = review_voice(tmp_path, episode_id, "B001", "candidate_03")
    second = review_voice(tmp_path, episode_id, "B002", "candidate_02")

    assert first["status"] == second["status"] == "SELECTED"
    value = load_yaml(episode_root / "audio" / "voice_manifest.yaml")
    assert value["takes"]["B001"]["selected"] == "candidate_03"
    assert value["takes"]["B002"]["selected"] == "candidate_02"


def test_voice_selection_rejects_invented_or_non_english_narrators(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "voxcpm2"
    for voice_id, language in (("voice_en", "en"), ("voice_zh", "zh")):
        voice_dir = project / "voices" / voice_id
        voice_dir.mkdir(parents=True)
        (voice_dir / "reference.wav").write_bytes(b"reference")
        (voice_dir / "voice.json").write_text(
            '{"id": "' + voice_id + '", "language": "' + language + '", "default_style": "neutral", "styles": {"neutral": {"reference": "reference.wav"}}, "authorization_status": "authorized", "commercial_use": true}',
            encoding="utf-8",
        )
    monkeypatch.setenv("VOXCPM_PROJECT", str(project))

    assert select_voice({"audio": {}}, narrator="invented")["status"] == "BLOCKED_NARRATOR_NOT_FOUND"
    assert select_voice({"audio": {}}, narrator="voice_zh")["status"] == "BLOCKED_ENGLISH_NARRATOR"
    assert select_voice({"audio": {}}, narrator="voice_en")["status"] == "READY"


def test_production_voice_check_rejects_temporary_and_stale_voice(tmp_path: Path) -> None:
    episode_root = tmp_path / "episodes" / "EP001_earth-stop"
    beat_script = episode_root / "creative" / "beat_script.yaml"
    dump_yaml({"schema_version": "beat-script-v2", "beats": [{"id": "B01", "narration": "Text"}]}, beat_script)
    output = episode_root / "audio" / "production" / "narration.wav"
    output.parent.mkdir(parents=True)
    output.write_bytes(b"wav")

    write_voice_manifest(episode_root, {"provider": VOICE_PROVIDER, "script_hash": script_hash(episode_root), "production_voice": {"provider": VOICE_PROVIDER, "status": "READY", "temporary": True, "path": str(output)}})
    blocked = production_voice_check(episode_root)
    assert blocked["pass"] is False
    assert "temporary_voice_is_not_allowed" in blocked["reason"]

    write_voice_manifest(episode_root, {"provider": VOICE_PROVIDER, "script_hash": "stale", "production_voice": {"provider": VOICE_PROVIDER, "status": "READY", "temporary": False, "path": str(output)}})
    stale = production_voice_check(episode_root)
    assert stale["pass"] is False
    assert "voice_script_hash_stale" in stale["reason"]


def test_voxcpm2_unavailable_is_blocked_without_fallback(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VOXCPM_PROJECT", str(tmp_path / "missing-voxcpm2"))
    from studio.voice.voxcpm2 import doctor

    result = doctor(tmp_path, "EP001_earth-stop")

    assert result["status"] == "BLOCKED_ENGLISH_NARRATOR"
    assert result["fallback"] is None
