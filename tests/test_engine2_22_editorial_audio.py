from pathlib import Path
import numpy as np


def write_test_wav(path: Path, samples: np.ndarray, sample_rate: int = 24000) -> None:
    import wave
    pcm = np.clip(samples, -0.95, 0.95)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes((pcm * 32767).astype("<i2").tobytes())


def test_visual_motif_does_not_use_narration_words():
    from video_farm.director_motion import _motif
    beat = {"spoken_text": "смартфон клавиатура автодополнение", "visual_description": "", "visual_type": "illustration"}
    assert _motif({"meaning": "", "purpose": ""}, beat) == "abstract"


def test_visual_labels_do_not_repeat_long_narration_phrase():
    from video_farm.director_motion import _clean_labels
    beat = {
        "spoken_text": "нейросеть последовательно выбирает вероятное продолжение текста",
        "on_screen_text": ["нейросеть последовательно выбирает вероятное продолжение текста", "Проверка источника"],
    }
    assert _clean_labels(beat) == ["Проверка источника"]


def test_master_audio_uses_real_music_without_procedural_tone(tmp_path: Path):
    import shutil
    import pytest
    from video_farm.director_audio import SAMPLE_RATE, build_master_audio
    seconds = 0.8
    time = np.arange(int(SAMPLE_RATE * seconds), dtype=np.float32) / SAMPLE_RATE
    voice = 0.18 * np.sin(2 * np.pi * 190 * time)
    music = 0.12 * np.sin(2 * np.pi * 330 * time)
    voice_path, music_path, output_path = tmp_path / "voice.wav", tmp_path / "music.wav", tmp_path / "master.wav"
    write_test_wav(voice_path, voice)
    write_test_wav(music_path, music)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("FFmpeg is not installed")
    report = build_master_audio(
        [{"scene_id": "s_001", "beat_id": "b01", "audio_path": str(voice_path)}],
        output_path, pause_seconds=0, music_path=music_path, ffmpeg=ffmpeg,
    )
    assert report["procedural_bed"] is False
    assert report["effect_count"] == 0
    assert report["music_track"]["path"] == str(music_path.resolve())
    assert output_path.is_file() and output_path.stat().st_size > 1000
