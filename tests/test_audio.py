from pathlib import Path

from studio.media.audio import transcript_diff
from studio.qc.engine import _locked_transcript


def test_transcript_diff_canonicalizes_spoken_number_phrase() -> None:
    result = transcript_diff("four hundred sixty-five meters in one second", "465 meters in one second")

    assert result["decision"] == "PASS"
    assert result["coverage"] == 1.0
    assert result["missing_words"] == []


def test_locked_transcript_reads_the_manifest_script_section(tmp_path: Path) -> None:
    script_path = tmp_path / "script" / "locked.md"
    script_path.parent.mkdir()
    script_path.write_text("# Script\n\n## Full temporary voiceover\n\n> One second.\n", encoding="utf-8")

    result = _locked_transcript(
        {"script": {"locked": True, "path": "script/locked.md"}},
        tmp_path,
    )

    assert result == "One second."
