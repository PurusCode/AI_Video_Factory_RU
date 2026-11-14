import json
import shutil
from types import SimpleNamespace

import pytest

from video_farm.pixabay_media import _candidate_score, fetch_pixabay


def test_pixabay_semantic_relevance_beats_popularity():
    query = "person typing on smartphone"
    relevant = {
        "tags": "person, typing, smartphone, mobile, hands",
        "likes": 3, "downloads": 12, "duration": 8,
    }
    irrelevant_popular = {
        "tags": "ocean, beach, sunset, travel",
        "likes": 50000, "downloads": 900000, "duration": 20,
    }
    score_relevant = _candidate_score(query, relevant, "video", {"width": 1280, "height": 720})
    score_irrelevant = _candidate_score(query, irrelevant_popular, "video", {"width": 1920, "height": 1080})
    assert score_relevant > score_irrelevant


def test_pixabay_resolution_breaks_relevance_tie():
    query = "old archive books"
    low = {"tags": "old archive books", "likes": 10, "downloads": 20}
    high = {"tags": "old archive books", "likes": 10, "downloads": 20}
    assert _candidate_score(query, high, "video", {"width": 1920, "height": 1080}) > \
           _candidate_score(query, low, "video", {"width": 640, "height": 360})


def test_pixabay_score_does_not_crash_on_missing_metadata():
    assert _candidate_score("typing computer", {}, "photo") == -1.0


def test_pixabay_rejects_unrelated_candidate_even_if_popular():
    unrelated = {"tags": "ocean beach sunset", "likes": 50000, "downloads": 900000}
    assert _candidate_score("person typing on smartphone", unrelated, "video") == -1.0


def test_pixabay_falls_back_when_all_results_are_unrelated(tmp_path, monkeypatch):
    class FakeResponse:
        status_code = 200
        def raise_for_status(self):
            return None
        def json(self):
            return {"hits": [{"tags": "ocean beach sunset", "likes": 50000,
                              "downloads": 900000, "largeImageURL": "https://example.invalid/image.jpg"}]}

    calls = []
    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        if "params" in kwargs:
            return FakeResponse()
        raise AssertionError("unrelated Pixabay result must not be downloaded")

    import video_farm.pixabay_media as pixabay_module
    monkeypatch.setattr(pixabay_module.requests, "get", fake_get)
    settings = SimpleNamespace(pixabay_api_key="test-key")
    assert fetch_pixabay(settings, "person typing on smartphone", "photo", tmp_path) is None
    assert len(calls) == 1


def test_motion_graphic_creates_h264_video_and_metadata(tmp_path):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("FFmpeg not installed")
    from video_farm.director_motion import render_motion_graphic

    settings = SimpleNamespace(ffmpeg=ffmpeg, fps=25)
    output = tmp_path / "motion.mp4"
    beat = {
        "spoken_text": "Токен — это кусочек слова, слог или даже один символ.",
        "visual_type": "illustration",
        "visual_description": "Последовательность токенов, которые по одному выбираются моделью.",
        "on_screen_text": ["Предсказание токена"],
    }
    path = render_motion_graphic(
        settings,
        {"id": "s_008", "meaning": "Объяснение токенизации"},
        beat, output, 2.4,
    )
    assert path.is_file() and path.stat().st_size > 1024
    metadata = json.loads(path.with_suffix(".mp4.meta.json").read_text(encoding="utf-8"))
    assert metadata["keyframe_count"] == 2
    assert metadata["description_rendered"] is False
    assert metadata["dimensions"] == [1920, 1080]
    assert abs(metadata["duration_seconds"] - 2.4) <= 1 / 25


def test_motion_graphic_uses_three_keyframes_for_longer_beats(tmp_path):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("FFmpeg not installed")
    from video_farm.director_motion import render_motion_graphic

    settings = SimpleNamespace(ffmpeg=ffmpeg, fps=25)
    output = tmp_path / "long_motion.mp4"
    beat = {
        "spoken_text": "Когда ты задаёшь вопрос, модель не заходит в архив, чтобы извлечь проверенный факт.",
        "visual_type": "illustration",
        "visual_description": "Архивные полки постепенно превращаются в сеть связей модели.",
        "on_screen_text": ["Архив", "Модель как процесс"],
    }
    render_motion_graphic(
        settings, {"id": "s_007", "meaning": "Модель — не база данных"},
        beat, output, 4.5,
    )
    metadata = json.loads(output.with_suffix(".mp4.meta.json").read_text(encoding="utf-8"))
    assert metadata["keyframe_count"] == 3
    assert metadata["transition"] == "editorial_cut"
    assert abs(metadata["duration_seconds"] - 4.5) <= 1 / 25
