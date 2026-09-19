"""Hajimi V2 command-line entry point."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .analytics.schema import initialize_record
from .config import load_yaml, write_json
from .creative import generate_creative_package, load_creative_context, save_creative_artifact, validate_creative_package, validate_script_package
from .generation.image import load_image_prompt_artifact, prepare_image_job, register_image_candidate, select_image_candidate, write_image_prompt_artifact
from .db import StateStore
from .manifest import EPISODE_RE, assert_valid_manifest, load_manifest, manifest_hash, manifest_input_hash, new_manifest, write_manifest
from .master import register_resolve_master
from .media.hashing import sha256_file
from .paths import StudioPaths, project_root
from .pipeline.animatic import record_animatic_review, run_animatic_gate
from .production import load_generation_plan_shot, record_generation_plan, validate_production_generation_plan
from .publish.youtube import preflight as youtube_preflight
from .publish.youtube import publish_doctor
from .publish.youtube import publish_status as youtube_status
from .publish.youtube import record_checks, record_upload_readback
from .qc.engine import record_human_playback, record_shot_review, run_episode_qc, run_master_qc, run_shot_qc
from .resolve.sync import record_resolve_readback, resolve_doctor, sync_episode
from .remote.h3 import h3_doctor, prepare_episode as prepare_h3_episode, pull_episode_result, remote_status as h3_remote_status, select_candidate as select_h3_candidate, submit_episode as submit_h3_episode
from .remote.contract import _asset_spec, _select_mode, h3_generation_duration
from .remote.prompt import write_h3_prompt_artifact
from .readiness import episode_readiness
from .roughcut import build_roughcut
from .skills import check_skill_updates, skills_doctor, skills_list, sync_skills
from .voice.director import build_voice_plan
from .voice.voxcpm2 import doctor as voice_doctor
from .voice.voxcpm2 import assemble_voice, list_available_voices, render_voice, review_voice, voice_status


def _paths(root_arg: str | None) -> StudioPaths:
    return StudioPaths(Path(root_arg).resolve() if root_arg else project_root())


def _print(value: Any, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(value, ensure_ascii=False, indent=2))
    elif isinstance(value, dict):
        for key, item in value.items():
            print(f"{key}: {item}")
    else:
        print(value)


def _load_episode(paths: StudioPaths, episode_id: str) -> tuple[dict[str, Any], Path]:
    path = paths.manifest(episode_id)
    manifest = load_manifest(path)
    assert_valid_manifest(manifest, path)
    return manifest, path


def _safe_episode_root(paths: StudioPaths, episode_id: str) -> Path:
    if not isinstance(episode_id, str) or not EPISODE_RE.fullmatch(episode_id):
        raise ValueError("episode_id is invalid")
    episode_root = paths.episode(episode_id).resolve()
    if not episode_root.is_relative_to(paths.root.resolve()):
        raise ValueError("episode path escapes the project root")
    return episode_root


def _cmd_new(args: argparse.Namespace, paths: StudioPaths) -> int:
    episode_root = paths.episode(args.episode_id)
    manifest_path = episode_root / "episode.yaml"
    if manifest_path.exists() and not args.force:
        raise FileExistsError(f"Episode already exists: {manifest_path}")
    manifest = new_manifest(args.episode_id)
    write_manifest(manifest, manifest_path)
    for name in ("research", "creative", "script", "storyboard", "animatic", "production", "shots", "edit", "audio", "qc", "master", "publish"):
        (episode_root / name).mkdir(parents=True, exist_ok=True)
    _print({"created": str(manifest_path.resolve())}, args.json)
    return 0


def _cmd_status(args: argparse.Namespace, paths: StudioPaths) -> int:
    manifest, manifest_path = _load_episode(paths, args.episode_id)
    store = StateStore(paths.state_db)
    store.sync_manifest(manifest, manifest_path, manifest_hash(manifest_path))
    episode_root = manifest_path.parent
    gate_path = episode_root / "animatic" / "gate.json"
    master_report = episode_root / "qc" / "master_report.json"
    gate = json.loads(gate_path.read_text(encoding="utf-8")) if gate_path.exists() else {}
    voice = voice_status(paths.root, args.episode_id)
    director_review = gate.get("director_review", {})
    director_status = director_review.get("status", "NOT_RUN") if isinstance(director_review, dict) else str(director_review)
    master_value = "NOT_RUN"
    if master_report.exists():
        report = json.loads(master_report.read_text(encoding="utf-8"))
        master_value = report.get("decision", "NOT_RUN")
        master_path = Path(str(report.get("master", "")))
        if not master_path.is_absolute():
            master_path = paths.root / master_path
        if report.get("manifest_sha256") != manifest_input_hash(manifest) or (
            report.get("master_sha256") and master_path.is_file() and sha256_file(master_path) != report.get("master_sha256")
        ):
            master_value = "STALE"
    payload = {
        "episode_id": args.episode_id,
        "manifest_status": manifest.get("status"),
        "manifest": str(manifest_path.resolve()),
        "shot_count": len(manifest.get("shots", [])),
        "hero_shot": manifest.get("creative", {}).get("hero_shot"),
        "animatic_gate": gate.get("decision", "NOT_RUN"),
        "automation_gate": gate.get("automation_gate", "NOT_RUN"),
        "director_review": director_status,
        "production_gate": gate.get("production_gate", "NOT_RUN"),
        "production_voice": voice.get("status", "NOT_INITIALIZED"),
        "master_qc": master_value,
        "database": str(paths.state_db.resolve()),
    }
    _print(payload, args.json)
    return 0


def _cmd_readiness(args: argparse.Namespace, paths: StudioPaths) -> int:
    result = episode_readiness(paths.root, args.episode_id)
    _print(result, args.json)
    return 0


def _cmd_research(args: argparse.Namespace, paths: StudioPaths) -> int:
    episode_root = _safe_episode_root(paths, args.episode_id)
    manifest_path = episode_root / "episode.yaml"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"episode manifest is missing: {manifest_path}")
    load_manifest(manifest_path)
    required = [episode_root / "research" / "topic_brief.md", episode_root / "research" / "fact_pack.md", episode_root / "research" / "reference_deconstruction.json"]
    missing = [str(path) for path in required if not path.exists()]
    payload = {
        "episode_id": args.episode_id,
        "stage": "research",
        "decision": "PASS" if not missing else "FAIL",
        "required_outputs": [str(path.relative_to(paths.root)) for path in required],
        "missing": [str(Path(item).relative_to(paths.root)) if Path(item).is_absolute() else item for item in missing],
    }
    write_json(payload, episode_root / "research" / "research_status.json")
    _print(payload, args.json)
    return 0 if not missing else 1


def _cmd_animatic(args: argparse.Namespace, paths: StudioPaths) -> int:
    gate = run_animatic_gate(args.episode_id, root=paths.root, force=args.force)
    _print(gate, args.json)
    return 0 if gate.get("production_gate") == "PASS" else 1


def _cmd_animatic_review(args: argparse.Namespace, paths: StudioPaths) -> int:
    result = record_animatic_review(
        args.episode_id,
        root=paths.root,
        approve=args.approve,
        reviewer=args.reviewer,
        notes=args.notes,
    )
    _print(result, args.json)
    return 0 if result.get("production_gate") == "PASS" else 1


def _cmd_creative(args: argparse.Namespace, paths: StudioPaths) -> int:
    if args.creative_command == "context":
        context = load_creative_context(paths.root, args.episode_id)
        destination = paths.episode(args.episode_id) / "creative" / "context_pack.yaml"
        save_creative_artifact(context, destination)
        result = {"status": "PASS", "episode_id": args.episode_id, "context_pack": str(destination)}
    elif args.creative_command == "script-validate":
        errors = validate_script_package(paths.episode(args.episode_id) / "creative")
        result = {"status": "PASS" if not errors else "FAIL", "episode_id": args.episode_id, "errors": errors}
    elif args.creative_command == "validate":
        errors = validate_creative_package(paths.episode(args.episode_id) / "creative")
        result = {"status": "PASS" if not errors else "FAIL", "episode_id": args.episode_id, "errors": errors}
    else:
        result = generate_creative_package(paths.root, args.episode_id, force=args.force, agent_dir=args.agent_dir)
    _print(result, args.json)
    return 0 if result.get("status") in {"PASS"} else 1


def _cmd_production(args: argparse.Namespace, paths: StudioPaths) -> int:
    episode_root = _safe_episode_root(paths, args.episode_id)
    if args.production_command == "plan-record":
        value = load_yaml(Path(args.file).expanduser())
        destination = record_generation_plan(episode_root, value)
        result = {"status": "PASS", "generation_plan": str(destination.relative_to(episode_root))}
    else:
        errors = validate_production_generation_plan(episode_root)
        result = {"status": "PASS" if not errors else "FAIL", "errors": errors}
    _print(result, args.json)
    return 0 if result["status"] == "PASS" else 1


def _cmd_image(args: argparse.Namespace, paths: StudioPaths) -> int:
    episode_root = paths.episode(args.episode_id)
    shot_dir = episode_root / "shots" / args.shot_id
    if args.image_command == "prompt-record":
        prompt = Path(args.prompt_file).expanduser().read_text(encoding="utf-8")
        style_decision = load_yaml(Path(args.style_decision).expanduser())
        result = write_image_prompt_artifact(
            episode_root,
            args.shot_id,
            prompt,
            style_decision,
            args.reference,
        )
    elif args.image_command == "prepare":
        shot = load_yaml(shot_dir / "shot.yaml")
        generation_plan = load_generation_plan_shot(episode_root, args.shot_id)
        shot["image_candidate_plan"] = {"candidates": generation_plan.get("image_candidates", 0)}
        prompt_artifact = load_image_prompt_artifact(episode_root, args.shot_id)
        job = prepare_image_job(shot, prompt_artifact=prompt_artifact)
        destination = shot_dir / "images" / "job.json"
        if destination.exists() and not args.force:
            raise FileExistsError(f"Image job already exists: {destination}; use --force after a new prompt decision")
        write_json(job, destination)
        result = {"status": "READY", "shot_id": args.shot_id, "job": str(destination.relative_to(episode_root))}
    elif args.image_command == "register":
        job_path = shot_dir / "images" / "job.json"
        job = json.loads(job_path.read_text(encoding="utf-8"))
        source = Path(args.source).expanduser()
        if not source.is_absolute():
            source = paths.root / source
        destination = register_image_candidate(
            episode_root,
            args.shot_id,
            source,
            job,
            candidate_number=args.candidate,
        )
        result = {"status": "REGISTERED", "candidate": str(destination.relative_to(episode_root))}
    else:
        destination = select_image_candidate(
            episode_root,
            args.shot_id,
            args.candidate,
            args.reviewer,
        )
        result = {"status": "SELECTED", "selected_keyframe": str(destination.relative_to(episode_root)), "reviewer": args.reviewer}
    _print(result, args.json)
    return 0


def _cmd_skills(args: argparse.Namespace) -> int:
    if args.skills_command == "doctor":
        result = skills_doctor()
    elif args.skills_command == "list":
        result = skills_list()
    elif args.skills_command == "updates":
        result = check_skill_updates()
    elif args.skills_command == "sync":
        result = sync_skills(args.skill or None)
    else:
        result = skills_doctor()
    _print(result, args.json)
    return 0 if result.get("status") == "PASS" else 1


def _cmd_voice(args: argparse.Namespace, paths: StudioPaths) -> int:
    if args.voice_command == "voices":
        result = {"status": "READY", "provider": "voxcpm2_local", "voices": list_available_voices()}
        _print(result, args.json)
        return 0
    if args.voice_command == "doctor":
        result = voice_doctor(paths.root, getattr(args, "episode_id", None), narrator=getattr(args, "narrator", None))
        _print(result, args.json)
        return 0 if result.get("status") in {"READY", "PARTIAL"} else 1
    if args.voice_command == "plan":
        result = build_voice_plan(paths.root, args.episode_id, narrator=getattr(args, "narrator", None))
    elif args.voice_command == "render":
        result = render_voice(paths.root, args.episode_id)
    elif args.voice_command == "review":
        result = review_voice(paths.root, args.episode_id, args.beat_id, args.select, reviewer=args.reviewer)
    elif args.voice_command == "assemble":
        result = assemble_voice(paths.root, args.episode_id, pause_seconds=args.pause_seconds)
    else:
        result = voice_status(paths.root, args.episode_id)
    _print(result, args.json)
    return 0 if result.get("status") in {"READY", "PLANNED", "SELECTED", "REVIEW_REQUIRED"} else 1


def _cmd_qc(args: argparse.Namespace, paths: StudioPaths) -> int:
    if args.qc_command == "shot":
        result = run_shot_qc(args.episode_id, args.shot_id, root=paths.root, force=args.force)
        decision = result.get("decision")
    elif args.qc_command == "review":
        result = record_shot_review(
            paths.root,
            args.episode_id,
            args.shot_id,
            decision=args.decision,
            reviewer=args.reviewer,
            notes=args.review_notes,
        )
        decision = result.get("decision")
    elif args.qc_command == "episode":
        result = run_episode_qc(args.episode_id, root=paths.root, force=args.force)
        decision = result.get("decision")
    else:
        result = run_master_qc(args.episode_id, root=paths.root, force=args.force)
        if getattr(args, "record_human_playback", False):
            result = record_human_playback(
                paths.root,
                args.episode_id,
                reviewer=getattr(args, "reviewer", "human"),
                notes=getattr(args, "review_notes", None),
            )
        decision = result.get("decision")
    _print(result, args.json)
    return 0 if decision in {"PASS", "REVIEW"} else 1


def _cmd_master(args: argparse.Namespace, paths: StudioPaths) -> int:
    manifest, _ = _load_episode(paths, args.episode_id)
    if not args.input:
        raise RuntimeError(
            "this command registers an optional Resolve export; pass --input <Resolve export>. "
            "The normal FFmpeg master is built with `hajimi roughcut build <episode_id>`."
        )
    source = Path(args.input)
    if not source.is_absolute():
        source = paths.root / source
    result = register_resolve_master(paths.episode(args.episode_id), manifest, source, force=args.force)
    _print(result, args.json)
    return 0


def _cmd_h3(args: argparse.Namespace, paths: StudioPaths) -> int:
    if args.h3_command == "doctor":
        result = h3_doctor(paths.root)
        _print(result, args.json)
        return 0 if result.get("status") == "PASS" else 1
    if args.h3_command == "prompt-record":
        if not args.shot:
            raise ValueError("h3 prompt-record requires --shot S001")
        manifest, _ = _load_episode(paths, args.episode_id)
        manifest_shot = next((item for item in manifest.get("shots", []) if item.get("id") == args.shot), None)
        if manifest_shot is None:
            raise ValueError(f"unknown shot: {args.shot}")
        shot_path = paths.episode(args.episode_id) / "shots" / args.shot / "shot.yaml"
        shot = load_yaml(shot_path)
        generation_plan = load_generation_plan_shot(paths.episode(args.episode_id), args.shot)
        mode = _select_mode(str(manifest_shot.get("method", shot.get("method", ""))), shot)
        input_strategy = generation_plan.get("input_strategy") if isinstance(generation_plan.get("input_strategy"), dict) else {}
        assets, _ = _asset_spec(paths.episode(args.episode_id), shot, mode, input_strategy)
        start, end = manifest_shot.get("time_start"), manifest_shot.get("time_end")
        edit_duration = float(end) - float(start) if isinstance(start, (int, float)) and isinstance(end, (int, float)) else manifest_shot.get("duration_target")
        if not isinstance(edit_duration, (int, float)) or isinstance(edit_duration, bool) or edit_duration <= 0:
            raise ValueError(f"{args.shot} timeline edit duration is required")
        generation_duration = h3_generation_duration(float(edit_duration), generation_plan.get("generation_duration_sec"))
        contract = shot.get("shot_contract") if isinstance(shot.get("shot_contract"), dict) else {}
        audio_intent = contract.get("audio_intent")
        if not isinstance(audio_intent, str) or not audio_intent.strip():
            raise ValueError(f"{args.shot} Shot Contract must author audio_intent before H3 prompt writing")
        music_value = contract.get("non_diegetic_music", shot.get("non_diegetic_music"))
        allow_music = isinstance(music_value, str) and bool(music_value.strip()) and music_value.strip() != "N/A"
        allow_narration = bool(contract.get("narration_requested"))
        allow_dialogue = bool(contract.get("dialogue_requested"))
        prompt = Path(args.prompt_file).expanduser().read_text(encoding="utf-8")
        artifact = write_h3_prompt_artifact(
            paths.episode(args.episode_id),
            args.shot,
            mode,
            prompt,
            audio_intent.strip(),
            [path for _, path in assets],
            generation_duration,
            job_revision=args.revision,
            allow_non_diegetic_music=allow_music,
            allow_narration=allow_narration,
            allow_dialogue=allow_dialogue,
        )
        result = {"status": "READY", "shot_id": args.shot, "mode": mode, "prompt": f"shots/{args.shot}/h3/prompt.txt", "prompt_source_contract_sha256": artifact["source_shot_contract_sha256"], "generation_duration_sec": generation_duration}
    elif args.h3_command == "prepare":
        result = {"jobs": [str(path.relative_to(paths.episode(args.episode_id))) for path in prepare_h3_episode(paths.root, args.episode_id, args.shot)]}
    elif args.h3_command == "submit":
        result = {"submitted": submit_h3_episode(paths.root, args.episode_id, args.shot)}
    elif args.h3_command == "status":
        result = h3_remote_status(paths.root, args.episode_id, args.shot)
    elif args.h3_command == "pull":
        if not args.shot:
            raise ValueError("h3 pull requires --shot S001")
        result = {"result_directory": str(pull_episode_result(paths.root, args.episode_id, args.shot))}
    else:
        if not args.shot:
            raise ValueError("h3 select requires --shot S001")
        selected = select_h3_candidate(paths.root, args.episode_id, args.shot, args.candidate, args.reviewer)
        result = {"selected": str(selected.relative_to(paths.episode(args.episode_id))), "reviewer": args.reviewer}
    _print(result, args.json)
    return 0


def _cmd_roughcut(args: argparse.Namespace, paths: StudioPaths) -> int:
    output = build_roughcut(paths.episode(args.episode_id))
    _print({"roughcut": str(output.relative_to(paths.episode(args.episode_id)))}, args.json)
    return 0


def _cmd_resolve_sync(args: argparse.Namespace, paths: StudioPaths) -> int:
    if args.resolve_command == "doctor":
        result = resolve_doctor(paths.root)
        _print(result, args.json)
        return 0 if result.get("status") == "READY" else 1
    if args.resolve_command == "sync":
        destination = sync_episode(paths.root, args.episode_id)
        _print({"handoff": str(destination.resolve()), "mutation": False}, args.json)
        return 0
    readback_path = Path(args.file)
    if not readback_path.is_absolute():
        readback_path = paths.root / readback_path
    readback = json.loads(readback_path.read_text(encoding="utf-8"))
    result = record_resolve_readback(paths.root, args.episode_id, readback)
    _print(result, args.json)
    return 0 if result.get("decision") == "PASS" else 1


def _cmd_publish(args: argparse.Namespace, paths: StudioPaths) -> int:
    if args.publish_command == "doctor":
        result = publish_doctor(paths.root, getattr(args, "episode_id", None))
    elif args.publish_command == "youtube":
        result = youtube_preflight(paths.root, args.episode_id, requested_visibility=args.visibility)
    elif args.publish_command == "record":
        readback_path = Path(args.file)
        if not readback_path.is_absolute():
            readback_path = paths.root / readback_path
        result = record_upload_readback(paths.root, args.episode_id, json.loads(readback_path.read_text(encoding="utf-8")))
    elif args.publish_command == "checks":
        checks_path = Path(args.file)
        if not checks_path.is_absolute():
            checks_path = paths.root / checks_path
        result = record_checks(paths.root, args.episode_id, json.loads(checks_path.read_text(encoding="utf-8")))
    else:
        result = youtube_status(paths.root, args.episode_id)
    _print(result, args.json)
    return 0 if result.get("status") in {"READY", "PREFLIGHT_READY", "NOT_INITIALIZED", "UPLOADED_PRIVATE", "CHECKS_RECORDED"} else 1


def _cmd_analytics(args: argparse.Namespace, paths: StudioPaths) -> int:
    destination = initialize_record(paths.root, args.episode_id)
    _print({"analytics_record": str(destination.resolve())}, args.json)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hajimi", description="Hajimi V2 studio pipeline")
    parser.add_argument("--root", help="project root override")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    sub = parser.add_subparsers(dest="command", required=True)

    new = sub.add_parser("new")
    new.add_argument("episode_id")
    new.add_argument("--force", action="store_true")
    new.add_argument("--json", action="store_true")

    for name in ("status", "research"):
        command = sub.add_parser(name)
        command.add_argument("episode_id")
        command.add_argument("--json", action="store_true")
    readiness = sub.add_parser("readiness", help="derive local, remote H3, and postproduction readiness")
    readiness.add_argument("episode_id")
    readiness.add_argument("--json", action="store_true")
    animatic = sub.add_parser("animatic")
    animatic.add_argument("episode_id")
    animatic.add_argument("--force", action="store_true")
    animatic.add_argument("--json", action="store_true")
    animatic_review = sub.add_parser("animatic-review", help="record director approval for the exact current animatic")
    animatic_review.add_argument("episode_id")
    review_decision = animatic_review.add_mutually_exclusive_group(required=True)
    review_decision.add_argument("--approve", action="store_true")
    review_decision.add_argument("--reject", action="store_false", dest="approve")
    animatic_review.add_argument("--reviewer", default="director")
    animatic_review.add_argument("--notes")
    animatic_review.add_argument("--json", action="store_true")

    creative = sub.add_parser("creative", help="build content-first creative artifacts")
    creative_sub = creative.add_subparsers(dest="creative_command", required=True)
    creative_context = creative_sub.add_parser("context")
    creative_context.add_argument("episode_id")
    creative_context.add_argument("--json", action="store_true")
    creative_package = creative_sub.add_parser("package")
    creative_package.add_argument("episode_id")
    creative_package.add_argument("--force", action="store_true")
    creative_package.add_argument("--agent-dir")
    creative_package.add_argument("--json", action="store_true")
    creative_validate = creative_sub.add_parser("validate")
    creative_validate.add_argument("episode_id")
    creative_validate.add_argument("--json", action="store_true")
    creative_script_validate = creative_sub.add_parser("script-validate")
    creative_script_validate.add_argument("episode_id")
    creative_script_validate.add_argument("--json", action="store_true")

    production = sub.add_parser("production", help="record and validate post-animatic production plans")
    production_sub = production.add_subparsers(dest="production_command", required=True)
    plan_record = production_sub.add_parser("plan-record")
    plan_record.add_argument("episode_id")
    plan_record.add_argument("--file", required=True)
    plan_record.add_argument("--json", action="store_true")
    plan_validate = production_sub.add_parser("plan-validate")
    plan_validate.add_argument("episode_id")
    plan_validate.add_argument("--json", action="store_true")

    image = sub.add_parser("image", help="record agent-authored GPT Image prompts and candidate provenance")
    image_sub = image.add_subparsers(dest="image_command", required=True)
    image_prompt = image_sub.add_parser("prompt-record")
    image_prompt.add_argument("episode_id")
    image_prompt.add_argument("shot_id")
    image_prompt.add_argument("--prompt-file", required=True)
    image_prompt.add_argument("--style-decision", required=True)
    image_prompt.add_argument("--reference", action="append", default=[])
    image_prompt.add_argument("--json", action="store_true")
    image_prepare = image_sub.add_parser("prepare")
    image_prepare.add_argument("episode_id")
    image_prepare.add_argument("--shot", dest="shot_id", required=True)
    image_prepare.add_argument("--force", action="store_true")
    image_prepare.add_argument("--json", action="store_true")
    image_register = image_sub.add_parser("register")
    image_register.add_argument("episode_id")
    image_register.add_argument("--shot", dest="shot_id", required=True)
    image_register.add_argument("--source", required=True)
    image_register.add_argument("--candidate", type=int, default=1)
    image_register.add_argument("--json", action="store_true")
    image_select = image_sub.add_parser("select")
    image_select.add_argument("episode_id")
    image_select.add_argument("--shot", dest="shot_id", required=True)
    image_select.add_argument("--candidate", type=int, required=True)
    image_select.add_argument("--reviewer", required=True)
    image_select.add_argument("--json", action="store_true")

    skills = sub.add_parser("skills", help="inspect and maintain the pinned shared Hajimi skill stack")
    skills_sub = skills.add_subparsers(dest="skills_command", required=True)
    for command_name in ("doctor", "list", "updates", "verify"):
        command = skills_sub.add_parser(command_name)
        command.add_argument("--json", action="store_true")
    skills_sync_parser = skills_sub.add_parser("sync")
    skills_sync_parser.add_argument("--skill", action="append")
    skills_sync_parser.add_argument("--json", action="store_true")

    voice = sub.add_parser("voice", help="plan and render production voice")
    voice_sub = voice.add_subparsers(dest="voice_command", required=True)
    voice_voices = voice_sub.add_parser("voices")
    voice_voices.add_argument("--json", action="store_true")
    voice_doctor_parser = voice_sub.add_parser("doctor")
    voice_doctor_parser.add_argument("episode_id", nargs="?")
    voice_doctor_parser.add_argument("--narrator")
    voice_doctor_parser.add_argument("--json", action="store_true")
    for name in ("plan", "render", "status"):
        command = voice_sub.add_parser(name)
        command.add_argument("episode_id")
        if name == "plan":
            command.add_argument("--narrator")
        command.add_argument("--json", action="store_true")
    voice_review = voice_sub.add_parser("review")
    voice_review.add_argument("episode_id")
    voice_review.add_argument("beat_id")
    voice_review.add_argument("--select", required=True)
    voice_review.add_argument("--reviewer", default="human")
    voice_review.add_argument("--json", action="store_true")
    voice_assemble = voice_sub.add_parser("assemble")
    voice_assemble.add_argument("episode_id")
    voice_assemble.add_argument("--pause-seconds", type=float, default=0.0)
    voice_assemble.add_argument("--json", action="store_true")

    qc = sub.add_parser("qc")
    qc_sub = qc.add_subparsers(dest="qc_command", required=True)
    shot = qc_sub.add_parser("shot")
    shot.add_argument("episode_id")
    shot.add_argument("shot_id")
    review = qc_sub.add_parser("review")
    review.add_argument("episode_id")
    review.add_argument("shot_id")
    review.add_argument("--decision", choices=("PASS", "REJECT"), default="PASS")
    review.add_argument("--reviewer", default="human")
    review.add_argument("--review-notes")
    episode = qc_sub.add_parser("episode")
    episode.add_argument("episode_id")
    master_qc = qc_sub.add_parser("master")
    master_qc.add_argument("episode_id")
    master_qc.add_argument("--record-human-playback", action="store_true")
    master_qc.add_argument("--reviewer", default="human")
    master_qc.add_argument("--review-notes")
    for command in (shot, episode, master_qc):
        command.add_argument("--force", action="store_true")
        command.add_argument("--json", action="store_true")
    review.add_argument("--json", action="store_true")

    master = sub.add_parser("master", help="register an optional Resolve premium-finish export as the active master")
    master.add_argument("episode_id")
    master.add_argument("--input")
    master.add_argument("--force", action="store_true")
    master.add_argument("--json", action="store_true")

    h3 = sub.add_parser("h3", help="prepare and operate remote ComfyUI MiniMax H3 jobs")
    h3_sub = h3.add_subparsers(dest="h3_command", required=True)
    h3_doctor_parser = h3_sub.add_parser("doctor")
    h3_doctor_parser.add_argument("--json", action="store_true")
    h3_prompt_record = h3_sub.add_parser("prompt-record", help="validate and persist a locally agent-authored official H3 prompt")
    h3_prompt_record.add_argument("episode_id")
    h3_prompt_record.add_argument("--shot", required=True)
    h3_prompt_record.add_argument("--prompt-file", required=True)
    h3_prompt_record.add_argument("--revision", type=int, default=1)
    h3_prompt_record.add_argument("--json", action="store_true")
    for name in ("prepare", "submit", "status", "pull"):
        command = h3_sub.add_parser(name)
        command.add_argument("episode_id")
        command.add_argument("--shot")
        command.add_argument("--json", action="store_true")
    h3_select = h3_sub.add_parser("select")
    h3_select.add_argument("episode_id")
    h3_select.add_argument("--shot", required=True)
    h3_select.add_argument("--candidate", type=int, required=True)
    h3_select.add_argument("--reviewer", required=True)
    h3_select.add_argument("--json", action="store_true")

    roughcut = sub.add_parser("roughcut", help="build the local FFmpeg rough master")
    roughcut_sub = roughcut.add_subparsers(dest="roughcut_command", required=True)
    roughcut_build = roughcut_sub.add_parser("build")
    roughcut_build.add_argument("episode_id")
    roughcut_build.add_argument("--json", action="store_true")

    resolve = sub.add_parser("resolve")
    resolve_sub = resolve.add_subparsers(dest="resolve_command", required=True)
    resolve_doctor_parser = resolve_sub.add_parser("doctor")
    resolve_doctor_parser.add_argument("--json", action="store_true")
    resolve_sync = resolve_sub.add_parser("sync")
    resolve_sync.add_argument("episode_id")
    resolve_sync.add_argument("--json", action="store_true")
    resolve_readback = resolve_sub.add_parser("readback")
    resolve_readback.add_argument("episode_id")
    resolve_readback.add_argument("--file", required=True)
    resolve_readback.add_argument("--json", action="store_true")

    publish = sub.add_parser("publish")
    publish_sub = publish.add_subparsers(dest="publish_command", required=True)
    publish_doctor_parser = publish_sub.add_parser("doctor")
    publish_doctor_parser.add_argument("episode_id", nargs="?")
    publish_doctor_parser.add_argument("--json", action="store_true")
    youtube = publish_sub.add_parser("youtube")
    youtube.add_argument("episode_id")
    youtube.add_argument("--private", dest="visibility", action="store_const", const="private", default="private")
    youtube.add_argument("--json", action="store_true")
    publish_record = publish_sub.add_parser("record")
    publish_record.add_argument("episode_id")
    publish_record.add_argument("--file", required=True)
    publish_record.add_argument("--json", action="store_true")
    publish_checks = publish_sub.add_parser("checks")
    publish_checks.add_argument("episode_id")
    publish_checks.add_argument("--file", required=True)
    publish_checks.add_argument("--json", action="store_true")
    publish_status_parser = publish_sub.add_parser("status")
    publish_status_parser.add_argument("episode_id")
    publish_status_parser.add_argument("--json", action="store_true")

    analytics = sub.add_parser("analytics")
    analytics_sub = analytics.add_subparsers(dest="analytics_command", required=True)
    analytics_init = analytics_sub.add_parser("init")
    analytics_init.add_argument("episode_id")
    analytics_init.add_argument("--json", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(raw_argv)
    paths = _paths(args.root)
    try:
        if args.command == "new":
            return _cmd_new(args, paths)
        if args.command == "status":
            return _cmd_status(args, paths)
        if args.command == "readiness":
            return _cmd_readiness(args, paths)
        if args.command == "research":
            return _cmd_research(args, paths)
        if args.command == "animatic":
            return _cmd_animatic(args, paths)
        if args.command == "animatic-review":
            return _cmd_animatic_review(args, paths)
        if args.command == "creative":
            return _cmd_creative(args, paths)
        if args.command == "production":
            return _cmd_production(args, paths)
        if args.command == "image":
            return _cmd_image(args, paths)
        if args.command == "skills":
            return _cmd_skills(args)
        if args.command == "voice":
            return _cmd_voice(args, paths)
        if args.command == "qc":
            return _cmd_qc(args, paths)
        if args.command == "master":
            return _cmd_master(args, paths)
        if args.command == "h3":
            return _cmd_h3(args, paths)
        if args.command == "roughcut":
            return _cmd_roughcut(args, paths)
        if args.command == "resolve":
            return _cmd_resolve_sync(args, paths)
        if args.command == "publish":
            return _cmd_publish(args, paths)
        if args.command == "analytics":
            return _cmd_analytics(args, paths)
    except (FileNotFoundError, FileExistsError, PermissionError, RuntimeError, ValueError) as exc:
        print(f"hajimi: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
