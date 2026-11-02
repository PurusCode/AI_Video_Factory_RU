from __future__ import annotations

import json
import subprocess
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest

from video_farm import tts
from video_farm.assemble import _validate_audio_manifest
from video_farm.common import write_json


def _write_wav(path: Path, *, sample_rate: int = 22050, frames: int = 2205) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(b"\x00\x00" * frames)


def _fake_settings(tmp_path: Path) -> SimpleNamespace:
    data_dir = tmp_path / "data"
    model_dir = data_dir / "models" / "piper"
    model_dir.mkdir(parents=True)
    (model_dir / "ru_RU-dmitri-medium.onnx").write_bytes(b"model" * 500)
    cfg = {"audio": {"sample_rate": 22050}, "test_note": "keep this config larger than the download guard " * 8}
    (model_dir / "ru_RU-dmitri-medium.onnx.json").write_text(json.dumps(cfg), encoding="utf-8")
    return SimpleNamespace(
        data_dir=data_dir,
        tts_speed=1.0,
        tts_engine="piper",
        tts_speaker="ru_RU-dmitri-medium",
        ffmpeg="ffmpeg",
    )


def test_synthesize_records_reproducible_manifest_and_one_wav_per_block(tmp_path, monkeypatch):
    settings = _fake_settings(tmp_path)
    script_path = tmp_path / "script.json"
    write_json(script_path, {
        "blocks": [
            {"id": "intro", "heading": "Вступление", "voice_text": "DeepSeek использует API."},
            {"id": "body", "heading": "Основная часть", "voice_text": "Есть 8 GB памяти."},
        ]
    })
    fake_exe = str(tmp_path / "piper")
    monkeypatch.setattr(tts.shutil, "which", lambda name: fake_exe if name == "piper" else None)

    sent_texts = []
    def fake_run(cmd, **kwargs):
        # Capture actual text that the TTS process would receive.
        sent_texts.append(kwargs.get("input"))
        # Ensure Russian UTF-8 text is also decoded as UTF-8 inside piper.exe on Windows.
        assert kwargs["encoding"] == "utf-8"
        assert kwargs["env"]["PYTHONUTF8"] == "1"
        assert kwargs["env"]["PYTHONIOENCODING"] == "utf-8"
        output_path = Path(cmd[cmd.index("--output_file") + 1])
        _write_wav(output_path)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(tts.subprocess, "run", fake_run)
    out_dir = tmp_path / "audio"
    manifest = tts.synthesize(settings, script_path, out_dir, speed=1.0)

    assert manifest["status"] == "complete"
    assert manifest["blocks_expected"] == 2
    assert [b["id"] for b in manifest["blocks"]] == ["intro", "body"]
    assert manifest["model_sha256"] and len(manifest["model_sha256"]) == 64
    assert manifest["config_sha256"] and len(manifest["config_sha256"]) == 64
    assert sent_texts == ["ДипСик использует эй пи ай.", "Есть восемь гигабайт памяти."]
    assert manifest["blocks"][0]["source_voice_text"] == "DeepSeek использует API."
    assert manifest["blocks"][0]["normalized_voice_text"] == sent_texts[0]
    assert manifest["blocks"][1]["unconverted_numeric_tokens"] == []    
    assert not any("остались числовые токены" in item for item in manifest["quality_warnings"])
    assert manifest["python_version"]
    assert manifest["generated_at_utc"].endswith("+00:00")
    for block in manifest["blocks"]:
        assert (out_dir / block["file"]).is_file()
        assert block["duration_seconds"] == 0.1
        assert block["sample_rate"] == 22050
        assert block["normalized_text_sha256"]
        assert block["source_voice_text_sha256"]
        assert "source_voice_text" in block and "normalized_voice_text" in block
        assert block["elapsed_seconds"] >= 0
    saved = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert saved["status"] == "complete"
    assert len(saved["blocks"]) == 2


def test_synthesize_rejects_empty_block_before_running_piper(tmp_path, monkeypatch):
    settings = _fake_settings(tmp_path)
    script_path = tmp_path / "script.json"
    write_json(script_path, {"blocks": [{"id": "empty", "voice_text": "   "}]})
    monkeypatch.setattr(tts.shutil, "which", lambda _: "/not-used/piper")
    with pytest.raises(ValueError, match="Пустой voice_text"):
        tts.synthesize(settings, script_path, tmp_path / "audio", speed=1.0)


def test_synthesize_rejects_duplicate_block_ids(tmp_path, monkeypatch):
    settings = _fake_settings(tmp_path)
    script_path = tmp_path / "script.json"
    write_json(script_path, {"blocks": [
        {"id": "same", "voice_text": "Первый блок."},
        {"id": "same", "voice_text": "Второй блок."},
    ]})
    monkeypatch.setattr(tts.shutil, "which", lambda _: "/not-used/piper")
    with pytest.raises(ValueError, match="Повторяется ID"):
        tts.synthesize(settings, script_path, tmp_path / "audio", speed=1.0)


@pytest.mark.parametrize("speed", [0.0, 0.49, 2.01, float("inf")])
def test_synthesize_rejects_invalid_speeds(tmp_path, speed):
    settings = _fake_settings(tmp_path)
    script_path = tmp_path / "script.json"
    write_json(script_path, {"blocks": [{"id": "intro", "voice_text": "Контрольный текст."}]})
    with pytest.raises(ValueError, match="Скорость TTS"):
        tts.synthesize(settings, script_path, tmp_path / "audio", speed=speed)


def test_audio_manifest_must_cover_every_script_block(tmp_path):
    audio_dir = tmp_path / "audio"
    _write_wav(audio_dir / "intro.wav")
    blocks = [{"id": "intro"}, {"id": "body"}]
    manifest = {"blocks": [{"id": "intro", "file": "intro.wav", "duration_seconds": 0.1}]}
    with pytest.raises(RuntimeError, match="не соответствует сценарию"):
        _validate_audio_manifest(blocks, manifest, audio_dir)


def test_audio_manifest_checks_declared_duration(tmp_path):
    audio_dir = tmp_path / "audio"
    _write_wav(audio_dir / "intro.wav")
    manifest = {"blocks": [{"id": "intro", "file": "intro.wav", "duration_seconds": 2.0}]}
    with pytest.raises(RuntimeError, match="не совпадает с манифестом"):
        _validate_audio_manifest([{"id": "intro"}], manifest, audio_dir)


def test_control_script_covers_the_required_speech_cases():
    root = Path(__file__).resolve().parents[1]
    script = json.loads((root / "data" / "piper_control_script.json").read_text(encoding="utf-8"))
    assert len(script["blocks"]) >= 4
    assert all(str(block.get("voice_text", "")).strip() for block in script["blocks"])
    joined = " ".join(block["voice_text"] for block in script["blocks"])
    for required in ("DeepSeek", "API", "CPU", "16.10.2026", "12.5%", "4 500 RUB", "букву ё"):
        assert required.casefold() in joined.casefold()


def test_synthesize_reports_failure_when_piper_is_missing(tmp_path, monkeypatch):
    import builtins

    settings = _fake_settings(tmp_path)
    script_path = tmp_path / "script.json"
    write_json(script_path, {"blocks": [{"id": "intro", "voice_text": "Контрольный текст."}]})
    monkeypatch.setattr(tts.shutil, "which", lambda _: None)
    # Avoid detecting a piper.exe installed into the active test virtualenv.
    monkeypatch.setattr(tts.sys, "executable", str(tmp_path / "python-without-piper"))
    original_import = builtins.__import__

    def import_without_piper(name, *args, **kwargs):
        if name == "piper":
            raise ImportError("intentionally hidden in test")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_piper)
    with pytest.raises(RuntimeError, match="Piper не найден"):
        tts.synthesize(settings, script_path, tmp_path / "audio", speed=1.0)


def test_synthesize_marks_manifest_failed_when_piper_wav_is_invalid(tmp_path, monkeypatch):
    settings = _fake_settings(tmp_path)
    script_path = tmp_path / "script.json"
    write_json(script_path, {"blocks": [{"id": "intro", "voice_text": "Контрольный текст."}]})
    monkeypatch.setattr(tts.shutil, "which", lambda _: str(tmp_path / "piper"))

    def fake_run(cmd, **kwargs):
        output_path = Path(cmd[cmd.index("--output_file") + 1])
        output_path.write_bytes(b"not a wav" * 10)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(tts.subprocess, "run", fake_run)
    out_dir = tmp_path / "audio"
    with pytest.raises(RuntimeError, match="WAV повреждён"):
        tts.synthesize(settings, script_path, out_dir, speed=1.0)
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"
    assert "error" in manifest


def test_description_does_not_claim_stock_sources_when_no_external_media_used(tmp_path):
    from video_farm.assemble import create_description

    script_path = tmp_path / "script.json"
    write_json(script_path, {"title": "Тестовый ролик", "blocks": [{"id": "intro", "heading": "Вступление", "kind": "body"}]})
    payload = create_description(script_path, tmp_path / "publish.txt", used_media=[])
    assert "Pexels" not in payload["description"]
    assert "Pixabay" not in payload["description"]
    assert payload["media_attribution_status"] == "NO_EXTERNAL_MEDIA_USED"
    assert "не использованы" in payload["media_attribution"]


def test_description_lists_only_media_reported_as_actually_used(tmp_path):
    from video_farm.assemble import create_description

    script_path = tmp_path / "script.json"
    write_json(script_path, {"title": "Тестовый ролик", "blocks": []})
    used = [{
        "kind": "broll", "file": "clip.mp4", "source": "Pexels",
        "page_url": "https://example.invalid/clip", "creator": "Test Creator",
        "creator_url": "https://example.invalid/creator", "query": "science",
    }]
    payload = create_description(script_path, tmp_path / "publish.txt", used_media=used)
    assert "Pexels — Test Creator; https://example.invalid/clip" in payload["description"]
    assert payload["broll_sources"] == ["Pexels"]
    assert payload["media_attribution_status"] == "REVIEW_REQUIRED"
    assert payload["used_media"] == used


def test_description_created_without_render_evidence_marks_media_unknown(tmp_path):
    from video_farm.assemble import create_description

    script_path = tmp_path / "script.json"
    write_json(script_path, {"title": "Черновик описания", "blocks": []})
    payload = create_description(script_path, tmp_path / "publish.txt")
    assert payload["media_attribution_status"] == "UNKNOWN_REVIEW_REQUIRED"
    assert "не определена" in payload["media_attribution"]
    assert "Pexels" not in payload["description"]
    assert "Pixabay" not in payload["description"]
