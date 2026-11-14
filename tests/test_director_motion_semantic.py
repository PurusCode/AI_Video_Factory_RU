from __future__ import annotations

import json
import shutil
from types import SimpleNamespace

import pytest

from video_farm.director_motion import (
    _motif,
    _semantic_motion_frame,
    render_motion_graphic,
)


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        ("Учебная симуляция интерфейса чат-бота. В поле ввода печатается запрос.", "chat"),
        ("Сияющий кристалл или золотой свиток возникает из потока цифровых данных.", "crystal"),
        ("Роботизированная рука ставит красную печать ВЕРНО на документ.", "stamp"),
        ("Поток двоичного кода искажается и превращается в цифровые волны.", "glitch"),
        ("Цифровая ловушка-капкан захлопывается перед потоком данных.", "trap"),
        ("Сложный механизм из шестерёнок начинает вращаться.", "mechanism"),
        ("Типографический акцент: слова кажется и возможно перечёркиваются.", "typography"),
        ("Сравнение двух концепций: база данных и динамичная нейронная сеть.", "comparison"),
    ],
)
def test_motif_routes_from_concrete_shot_description(description, expected):
    # Scene context intentionally says hallucination: it must not override the shot.
    scene = {"meaning": "Галлюцинации и уверенная ложь", "purpose": "Показать риск ошибки"}
    beat = {"spoken_text": "Нейросеть уверенно отвечает на вопрос.", "visual_description": description}
    assert _motif(scene, beat) == expected


def test_motif_uses_scene_context_only_after_shot_and_speech():
    scene = {"meaning": "Архив и база данных", "purpose": "Показать хранение"}
    beat = {"spoken_text": "Абстрактная мысль.", "visual_description": "Нейтральная композиция"}
    assert _motif(scene, beat) == "archive"


def test_motif_uses_visual_type_fallback_for_text():
    assert _motif({}, {"visual_type": "text", "visual_description": "Акцент"}) == "typography"


@pytest.mark.parametrize("motif", ["chat", "crystal", "stamp", "glitch", "trap", "mechanism", "typography", "comparison"])
def test_semantic_animation_frames_change_over_time(motif):
    beat = {
        "spoken_text": "Роботизированная рука ставит печать на документ.",
        "visual_description": "Конкретная визуальная инструкция для сцены.",
        "on_screen_text": ["Проверка"]
    }
    frames = [_semantic_motion_frame(motif, beat, t) for t in (0.0, 0.5, 1.0)]
    thumbnails = [frame.resize((64, 36)).tobytes() for frame in frames]
    assert len(set(thumbnails)) == 3


def test_semantic_motif_renders_continuous_h264_animation(tmp_path):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("FFmpeg not installed")
    output = tmp_path / "stamp_motion.mp4"
    beat = {
        "spoken_text": "Нейросеть уверенно преподносит ошибку как факт.",
        "visual_type": "illustration",
        "visual_description": "Роботизированная рука ставит печать ВЕРНО на документ.",
        "on_screen_text": ["Уверенный ответ"],
    }
    result = render_motion_graphic(
        SimpleNamespace(ffmpeg=ffmpeg, fps=25),
        {"id": "s_003", "meaning": "Галлюцинации"},
        beat,
        output,
        1.2,
    )
    assert result.is_file() and result.stat().st_size > 1024
    metadata = json.loads(output.with_suffix(".mp4.meta.json").read_text(encoding="utf-8"))
    assert metadata["visual_family"] == "stamp"
    assert metadata["animation_mode"] == "procedural_object_motion"
    assert metadata["motif_routing"] == "shot_visual_description_first"
    assert metadata["motion_frame_count"] >= 20
    assert metadata["frame_count"] == 30
    assert metadata["description_rendered"] is False
