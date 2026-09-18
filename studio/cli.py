"""Hajimi V2 command-line entry point."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .analytics.schema import initialize_record
from .blender_stack import BlenderStackError, run_blender_command
from .config import write_json
from .db import StateStore
from .manifest import assert_valid_manifest, load_manifest, manifest_hash, new_manifest, write_manifest
from .master import register_resolve_master
from .paths import StudioPaths, project_root
from .pipeline.animatic import run_animatic_gate
from .publish.youtube import preflight as youtube_preflight
from .publish.youtube import publish_status as youtube_status
from .publish.youtube import record_checks, record_upload_readback
from .qc.engine import record_human_playback, record_shot_review, run_episode_qc, run_master_qc, run_shot_qc
from .resolve.sync import record_resolve_readback, sync_episode


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


def _cmd_new(args: argparse.Namespace, paths: StudioPaths) -> int:
    episode_root = paths.episode(args.episode_id)
    manifest_path = episode_root / "episode.yaml"
    if manifest_path.exists() and not args.force:
        raise FileExistsError(f"Episode already exists: {manifest_path}")
    manifest = new_manifest(args.episode_id)
    write_manifest(manifest, manifest_path)
    for name in ("research", "script", "storyboard", "animatic", "shots", "edit", "audio", "qc", "master", "publish"):
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
    payload = {
        "episode_id": args.episode_id,
        "manifest_status": manifest.get("status"),
        "manifest": str(manifest_path.resolve()),
        "shot_count": len(manifest.get("shots", [])),
        "hero_shot": manifest.get("creative", {}).get("hero_shot"),
        "animatic_gate": json.loads(gate_path.read_text(encoding="utf-8")).get("decision") if gate_path.exists() else "NOT_RUN",
        "master_qc": json.loads(master_report.read_text(encoding="utf-8")).get("decision") if master_report.exists() else "NOT_RUN",
        "database": str(paths.state_db.resolve()),
    }
    _print(payload, args.json)
    return 0


def _cmd_research(args: argparse.Namespace, paths: StudioPaths) -> int:
    _, manifest_path = _load_episode(paths, args.episode_id)
    episode_root = manifest_path.parent
    required = [episode_root / "research" / "topic_brief.md", episode_root / "research" / "fact_pack.md", episode_root / "research" / "reference_deconstruction.json"]
    missing = [str(path) for path in required if not path.exists()]
    payload = {"episode_id": args.episode_id, "stage": "research", "decision": "PASS" if not missing else "FAIL", "required_outputs": [str(path) for path in required], "missing": missing}
    write_json(payload, episode_root / "research" / "research_status.json")
    _print(payload, args.json)
    return 0 if not missing else 1


def _cmd_animatic(args: argparse.Namespace, paths: StudioPaths) -> int:
    gate = run_animatic_gate(args.episode_id, root=paths.root, force=args.force)
    _print(gate, args.json)
    return 0 if gate.get("decision") == "PASS" else 1


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
            "a Resolve-exported master is required; pass --input <Resolve export> "
            "(the animatic release candidate is not a publishable master)"
        )
    source = Path(args.input)
    if not source.is_absolute():
        source = paths.root / source
    result = register_resolve_master(paths.episode(args.episode_id), manifest, source, force=args.force)
    _print(result, args.json)
    return 0


def _cmd_resolve_sync(args: argparse.Namespace, paths: StudioPaths) -> int:
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
    if args.publish_command == "youtube":
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
    return 0 if result.get("status") in {"READY", "NOT_INITIALIZED", "UPLOADED_PRIVATE", "CHECKS_RECORDED"} else 1


def _cmd_analytics(args: argparse.Namespace, paths: StudioPaths) -> int:
    destination = initialize_record(paths.root, args.episode_id)
    _print({"analytics_record": str(destination.resolve())}, args.json)
    return 0


def _cmd_blender(args: argparse.Namespace, paths: StudioPaths) -> int:
    result = run_blender_command(
        paths.root,
        args.blender_command,
        getattr(args, "target", None),
        getattr(args, "shot_id", None),
        profile=getattr(args, "profile", None),
        force=getattr(args, "force", False),
        start=getattr(args, "start", None),
        end=getattr(args, "end", None),
        resume=not getattr(args, "no_resume", False),
    )
    _print(result, args.json)
    return 0 if result.get("decision", result.get("status")) not in {"FAIL", "BLOCKED_NO_SEQUENCE", "BLOCKED_PREFLIGHT"} else 1


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
    animatic = sub.add_parser("animatic")
    animatic.add_argument("episode_id")
    animatic.add_argument("--force", action="store_true")
    animatic.add_argument("--json", action="store_true")

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

    master = sub.add_parser("master")
    master.add_argument("episode_id")
    master.add_argument("--input")
    master.add_argument("--force", action="store_true")
    master.add_argument("--json", action="store_true")

    resolve = sub.add_parser("resolve")
    resolve_sub = resolve.add_subparsers(dest="resolve_command", required=True)
    resolve_sync = resolve_sub.add_parser("sync")
    resolve_sync.add_argument("episode_id")
    resolve_sync.add_argument("--json", action="store_true")
    resolve_readback = resolve_sub.add_parser("readback")
    resolve_readback.add_argument("episode_id")
    resolve_readback.add_argument("--file", required=True)
    resolve_readback.add_argument("--json", action="store_true")

    publish = sub.add_parser("publish")
    publish_sub = publish.add_subparsers(dest="publish_command", required=True)
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

    blender = sub.add_parser("blender", help="project-local headless Blender stack")
    blender_sub = blender.add_subparsers(dest="blender_command", required=True)
    for name in ("doctor", "bootstrap", "benchmark", "configure_gpu", "configure_assets", "configure_render"):
        command = blender_sub.add_parser(name)
        command.add_argument("--json", action="store_true")
    for name in ("build", "preview", "render", "qc"):
        command = blender_sub.add_parser(name)
        command.add_argument("target", help="EP001_TEST_01 or an episode key such as EP001")
        command.add_argument("shot_id", nargs="?", help="episode shot id, e.g. S005")
        if name in {"preview", "render", "qc"}:
            command.add_argument("--profile", choices=("P0", "P1", "P2", "P3", "hero_exr", "final_cycles"))
        if name in {"build", "preview", "render"}:
            command.add_argument("--force", action="store_true")
        if name in {"preview", "render"}:
            command.add_argument("--start", type=int)
            command.add_argument("--end", type=int)
            command.add_argument("--no-resume", action="store_true")
        command.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    paths = _paths(args.root)
    try:
        if args.command == "new":
            return _cmd_new(args, paths)
        if args.command == "status":
            return _cmd_status(args, paths)
        if args.command == "research":
            return _cmd_research(args, paths)
        if args.command == "animatic":
            return _cmd_animatic(args, paths)
        if args.command == "qc":
            return _cmd_qc(args, paths)
        if args.command == "master":
            return _cmd_master(args, paths)
        if args.command == "resolve":
            return _cmd_resolve_sync(args, paths)
        if args.command == "publish":
            return _cmd_publish(args, paths)
        if args.command == "analytics":
            return _cmd_analytics(args, paths)
        if args.command == "blender":
            return _cmd_blender(args, paths)
    except (BlenderStackError, FileNotFoundError, FileExistsError, PermissionError, RuntimeError, ValueError) as exc:
        print(f"hajimi: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
