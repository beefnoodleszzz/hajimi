from pathlib import Path

from studio.media.audio import validate_sound_layers


def test_sound_layer_contract_requires_all_final_stems_and_hashes(tmp_path: Path) -> None:
    episode_root = tmp_path / "episodes" / "EP001_contract"
    final = episode_root / "audio" / "final"
    final.mkdir(parents=True)
    paths = {}
    for role in ("voiceover", "music", "ambience", "narrative_sfx"):
        path = final / f"{role}.wav"
        path.write_bytes(role.encode("utf-8"))
        paths[role] = path

    result = validate_sound_layers(
        tmp_path,
        episode_root,
        {"audio": {"required_layers": list(paths)}},
        stems={
            "stems": [
                {
                    "role": role,
                    "output": f"episodes/EP001_contract/audio/final/{role}.wav",
                    "output_sha256": __import__("hashlib").sha256(path.read_bytes()).hexdigest(),
                }
                for role, path in paths.items()
            ]
        },
    )

    assert result["decision"] == "PASS"
    assert result["required_layers"] == list(paths)
