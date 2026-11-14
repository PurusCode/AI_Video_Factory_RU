from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from video_farm import director_shots, pixabay_media, production_director


class _SearchResponse:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _DownloadResponse:
    headers = {"Content-Length": "2048"}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def raise_for_status(self):
        return None

    def iter_content(self, _chunk_size):
        yield b"x" * 2048


def _fake_hit(kind="photo"):
    return {
        "id": 123,
        "type": kind,
        "tags": "computer office technology",
        "largeImageURL": "https://cdn.example.test/computer.jpg",
        "webformatURL": "https://cdn.example.test/computer-small.jpg",
        "imageWidth": 1920,
        "imageHeight": 1080,
        "pageURL": "https://pixabay.com/photos/example-123/",
        "user": "ExampleCreator",
    }


def test_photo_search_explicitly_requests_real_photos(tmp_path, monkeypatch):
    captured = {}

    def fake_get(url, **kwargs):
        if kwargs.get("stream"):
            return _DownloadResponse()
        captured["url"] = url
        captured["params"] = kwargs["params"]
        return _SearchResponse({"hits": [_fake_hit("photo")]})

    monkeypatch.setattr(pixabay_media.requests, "get", fake_get)
    settings = SimpleNamespace(pixabay_api_key="test-key")
    result = pixabay_media.fetch_pixabay(settings, "computer office technology", "photo", tmp_path)

    assert captured["url"] == "https://pixabay.com/api/"
    assert captured["params"]["image_type"] == "photo"
    assert captured["params"]["min_width"] == 1280
    assert captured["params"]["min_height"] == 720
    assert result is not None
    assert result["media_type"] == "image"
    assert result["pixabay_type"] == "photo"
    assert Path(result["path"]).is_file()


def test_video_search_does_not_send_image_filters(tmp_path, monkeypatch):
    captured = {}

    def fake_get(url, **kwargs):
        if kwargs.get("stream"):
            return _DownloadResponse()
        captured["url"] = url
        captured["params"] = kwargs["params"]
        return _SearchResponse({
            "hits": [{
                "id": 456,
                "tags": "person typing computer",
                "duration": 10,
                "videos": {"medium": {"url": "https://cdn.example.test/typing.mp4", "width": 1920, "height": 1080}},
                "pageURL": "https://pixabay.com/videos/example-456/",
                "user": "ExampleCreator",
            }]
        })

    monkeypatch.setattr(pixabay_media.requests, "get", fake_get)
    settings = SimpleNamespace(pixabay_api_key="test-key")
    result = pixabay_media.fetch_pixabay(settings, "person typing computer", "video", tmp_path)

    assert captured["url"] == "https://pixabay.com/api/videos/"
    assert "image_type" not in captured["params"]
    assert "min_width" not in captured["params"]
    assert result is not None
    assert result["media_type"] == "video"


def test_shot_planner_must_preserve_approved_photo_type():
    source = [{
        "spoken_text": "A person is working at a computer.",
        "visual_type": "photo",
        "asset_strategy": "stock",
        "provider_id": "pixabay",
    }]
    changed_shot = [{
        "source_beat_id": "b01",
        "shot_id": "b01_s01",
        "spoken_text": "A person is working at a computer.",
        "visual_type": "illustration",
        "asset_strategy": "rendered",
        "provider_id": "internal_renderer",
    }]

    with pytest.raises(ValueError, match="must preserve visual_type/asset_strategy/provider_id"):
        director_shots._check_group_coverage(source, changed_shot, "s_001")


def test_shot_planner_accepts_preserved_photo_type():
    source = [{
        "spoken_text": "A person is working at a computer.",
        "visual_type": "photo",
        "asset_strategy": "stock",
        "provider_id": "pixabay",
    }]
    shot = [{
        "source_beat_id": "b01",
        "shot_id": "b01_s01",
        "spoken_text": "A person is working at a computer.",
        "visual_type": "photo",
        "asset_strategy": "stock",
        "provider_id": "pixabay",
    }]
    director_shots._check_group_coverage(source, shot, "s_001")


def test_photo_policy_is_present_in_director_and_critic_prompts():
    assert "PHOTO_EDITORIAL_POLICY_ENGINE_2_3" in production_director.DIRECTOR_SYSTEM
    assert "PHOTO_SELECTION_REVIEW_ENGINE_2_3" in production_director.CRITIC_SYSTEM
    assert "PHOTO_SELECTION_REPAIR_ENGINE_2_3" in production_director.REPAIR_SYSTEM
    assert "SHOT_TYPE_INHERITANCE_ENGINE_2_3" in director_shots.SYSTEM_PROMPT


def test_media_mix_summary_separates_stock_photos_videos_and_local_graphics():
    summary = production_director._summarize_media_mix([
        {"source": "Pixabay", "media_type": "image"},
        {"source": "Pixabay", "media_type": "video"},
        {"source": "AI Video Factory local renderer", "media_type": "video"},
    ])
    assert summary == {
        "total_assets": 3,
        "pixabay_photos": 1,
        "pixabay_videos": 1,
        "local_motion_graphics": 1,
        "other_assets": 0,
    }
