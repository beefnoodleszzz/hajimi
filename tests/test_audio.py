import sys
from pathlib import Path
from types import SimpleNamespace

from studio.media.audio import audio_qc, transcript_diff
from studio.qc.engine import _locked_transcript


def test_transcript_diff_canonicalizes_spoken_number_phrase() -> None:
    result = transcript_diff("four hundred sixty-five meters in one second", "465 meters in one second")

    assert result["decision"] == "PASS"
    assert result["coverage"] == 1.0
    assert result["missing_words"] == []


def test_transcript_diff_keeps_cjk_characters_for_multilingual_qc() -> None:
    result = transcript_diff("地面停止一秒", "地面停止一秒")

    assert result["expected_word_count"] == 6
    assert result["coverage"] == 1.0
    assert result["decision"] == "PASS"


def test_audio_qc_marks_detected_language_mismatch(monkeypatch, tmp_path: Path) -> None:
    class FakeWhisperModel:
        def __init__(self, *_args, **_kwargs):
            pass

        def transcribe(self, _path, vad_filter=True):
            return [SimpleNamespace(text="地面停止一秒")], SimpleNamespace(language="zh")

    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=FakeWhisperModel))
    monkeypatch.setattr(
        "studio.media.audio.probe_media",
        lambda _path: {"ok": True, "streams": [{"codec_type": "audio"}], "audio": {}},
    )

    result = audio_qc(tmp_path / "voice.wav", expected_transcript="The ground stops", expected_language="en-US")

    assert result["asr"]["language"] == "zh"
    assert result["asr"]["language_match"] is False
    assert result["asr"]["status"] == "REVIEW"


def test_locked_transcript_reads_the_manifest_script_section(tmp_path: Path) -> None:
    script_path = tmp_path / "script" / "locked.md"
    script_path.parent.mkdir()
    script_path.write_text("# Script\n\n## Full temporary voiceover\n\n> One second.\n", encoding="utf-8")

    result = _locked_transcript(
        {"script": {"locked": True, "path": "script/locked.md"}},
        tmp_path,
    )

    assert result == "One second."
