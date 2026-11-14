from __future__ import annotations

from types import SimpleNamespace

from video_farm import director_assembler as assembler


def _settings():
    return SimpleNamespace(width=1920, height=1080, fps=25, ffmpeg="ffmpeg", ffprobe="ffprobe")


def test_render_segment_loops_video_input_and_uses_requested_duration(tmp_path, monkeypatch):
    source = tmp_path / "motion.mp4"
    source.write_bytes(b"test video placeholder")
    commands = []
    monkeypatch.setattr(assembler, "_run", lambda command: commands.append(command))

    assembler._render_segment(
        _settings(),
        {"visual_path": str(source), "media_type": "video", "motion": "slow_zoom", "transition_in": "cut"},
        1.2345,
        tmp_path / "segment.mp4",
    )

    command = commands[0]
    assert command[command.index("-stream_loop") + 1] == "-1"
    assert command[command.index("-i") + 1] == str(source)
    assert command[command.index("-t") + 1] == "1.2345"
    assert "zoompan" not in " ".join(command)


def test_assemble_director_video_preserves_shot_order_timing_and_edl_provenance(tmp_path, monkeypatch):
    rendered = []
    ffmpeg_commands = []

    def fake_render(_settings, beat, duration, output):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"segment placeholder")
        rendered.append((beat, duration))

    def fake_probe(_ffprobe, _path):
        return {
            "format": {"duration": "3.12", "size": 1024},
            "streams": [
                {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080},
                {"codec_type": "audio", "codec_name": "aac", "sample_rate": "44100", "channels": 2},
            ],
        }

    monkeypatch.setattr(assembler, "_render_segment", fake_render)
    monkeypatch.setattr(assembler, "_run", lambda command: ffmpeg_commands.append(command))
    monkeypatch.setattr(assembler, "_probe", fake_probe)

    beats = [
        {
            "scene_id": "s_001", "beat_id": "b01", "shot_id": "b01_s01",
            "source_beat_id": "b01", "cut_reason": "Первый визуальный аргумент",
            "audio_duration_sec": 1.0, "audio_path": "audio_1.wav",
            "visual_path": "visual_1.mp4", "source": "AI Video Factory local renderer",
            "spoken_text": "Первая фраза.",
        },
        {
            "scene_id": "s_001", "beat_id": "b02", "shot_id": "b01_s02",
            "source_beat_id": "b01", "cut_reason": "Второй визуальный аргумент",
            "audio_duration_sec": 2.0, "audio_path": "audio_2.wav",
            "visual_path": "visual_2.mp4", "source": "AI Video Factory local renderer",
            "spoken_text": "Вторая фраза.",
        },
    ]

    report = assembler.assemble_director_video(
        _settings(), beats, tmp_path / "audio_master.wav", tmp_path / "final.mp4",
        tmp_path / "assembly", pause_seconds=0.12,
    )

    assert report["status"] == "passed"
    assert [item[0]["shot_id"] for item in rendered] == ["b01_s01", "b01_s02"]
    assert rendered[0][1] == 1.12
    assert rendered[1][1] == 5.0
    assert report["timeline"][0]["shot_id"] == "b01_s01"
    assert report["timeline"][0]["source_beat_id"] == "b01"
    assert report["timeline"][0]["cut_reason"] == "Первый визуальный аргумент"
    assert report["timeline"][1]["shot_id"] == "b01_s02"
    assert report["timeline"][1]["start_sec"] == 1.12
    assert report["timeline"][1]["end_sec"] == 3.12
    assert "-shortest" in ffmpeg_commands[-1]
    assert (tmp_path / "final.timeline.json").is_file()
