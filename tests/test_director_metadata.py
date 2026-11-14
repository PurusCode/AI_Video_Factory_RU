from __future__ import annotations

import wave
from types import SimpleNamespace

from video_farm import production_director as director


def test_produce_preserves_shot_edl_metadata(tmp_path, monkeypatch):
    def fake_synthesize(_settings, prepared, out_dir, _speed):
        out_dir.mkdir(parents=True, exist_ok=True)
        blocks = []
        for index, (block_id, _meta, _raw, _normalized) in enumerate(prepared, 1):
            filename = f"{index:02d}_{block_id}.wav"
            with wave.open(str(out_dir / filename), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(24000)
                wav.writeframes(b"\x00\x00" * 24000)
            blocks.append({"id": block_id, "file": filename})
        return {"status": "complete", "blocks": blocks}

    visual = tmp_path / "shot.mp4"
    visual.write_bytes(b"visual placeholder")

    def fake_asset(_settings, _scene, _beat, _visuals_dir, _warnings, _index, duration):
        assert duration == 1.0
        return {
            "path": str(visual), "media_type": "video",
            "source": "AI Video Factory local renderer", "sha256": "test-sha",
        }

    monkeypatch.setattr(director, "normalize_for_speech", lambda text: text)
    monkeypatch.setattr(director, "synthesize_kokoro", fake_synthesize)
    monkeypatch.setattr(director, "_asset_for_beat", fake_asset)

    settings = SimpleNamespace(tts_engine="kokoro", tts_speaker="dima")
    scenes = [{"id": "s_001", "meaning": "Смысл сцены"}]
    plans = [{
        "scene_id": "s_001", "music_cue": "", "beats": [{
            "spoken_text": "Точная фраза для этого монтажного плана.",
            "shot_id": "b01_s02", "source_beat_id": "b01",
            "cut_reason": "Переход к следующему визуальному аргументу",
        }],
    }]

    beats, report = director._produce(settings, scenes, plans, tmp_path / "production", 0.9)

    assert report["status"] == "complete"
    assert beats[0]["shot_id"] == "b01_s02"
    assert beats[0]["source_beat_id"] == "b01"
    assert beats[0]["cut_reason"] == "Переход к следующему визуальному аргументу"
