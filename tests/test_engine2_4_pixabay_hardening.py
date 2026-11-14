from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

from video_farm import pixabay_media, production_director


class SearchResponse:
    status_code = 200
    headers = {}

    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class DownloadResponse:
    status_code = 200

    def __init__(self, body=b"x" * 2048, headers=None):
        self.body = body
        self.headers = headers or {"Content-Length": str(len(body))}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def iter_content(self, _chunk_size):
        yield self.body


def video_hit(hit_id: int, tags: str, url: str, *, likes: int = 1):
    return {
        "id": hit_id,
        "tags": tags,
        "likes": likes,
        "downloads": 1,
        "duration": 8,
        "pageURL": f"https://pixabay.com/videos/test-{hit_id}/",
        "user": "TestCreator",
        "videos": {"large": {"url": url, "width": 1920, "height": 1080}},
    }


def test_pixabay_search_results_are_cached_for_24_hours(tmp_path, monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        if kwargs.get("stream"):
            return DownloadResponse()
        return SearchResponse({"hits": [video_hit(11, "person typing keyboard laptop", "https://cdn.test/11.mp4")]})

    monkeypatch.setattr(pixabay_media.requests, "get", fake_get)
    settings = SimpleNamespace(pixabay_api_key="test-key", cache_dir=tmp_path / "cache")

    first = pixabay_media.fetch_pixabay(settings, "person typing keyboard", "video", tmp_path / "media")
    second = pixabay_media.fetch_pixabay(settings, "person typing keyboard", "video", tmp_path / "media")

    assert first and second
    assert first["path"] == second["path"]
    # One API search + one download total; second call uses both search and file cache.
    assert len(calls) == 2
    cache_files = list((tmp_path / "cache" / "pixabay" / "search").glob("*.json"))
    assert len(cache_files) == 1
    cached = json.loads(cache_files[0].read_text(encoding="utf-8"))
    assert "payload" in cached and "cached_at" in cached


def test_pixabay_compares_results_from_all_queries_and_downloads_only_best(tmp_path, monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        if kwargs.get("stream"):
            return DownloadResponse()
        query = kwargs["params"]["q"]
        if query == "typing hands":
            return SearchResponse({"hits": [video_hit(21, "typing keyboard", "https://cdn.test/21.mp4")]})
        return SearchResponse({"hits": [video_hit(22, "person typing keyboard laptop hands", "https://cdn.test/22.mp4")]})

    monkeypatch.setattr(pixabay_media.requests, "get", fake_get)
    settings = SimpleNamespace(pixabay_api_key="test-key", cache_dir=tmp_path / "cache")

    result = pixabay_media.fetch_pixabay(
        settings, ["typing keyboard closeup", "person typing keyboard laptop hands"], "video", tmp_path / "media"
    )

    assert result is not None
    assert result["source_url"].endswith("test-22/")
    search_calls = [call for call in calls if "params" in call[1]]
    download_calls = [call for call in calls if call[1].get("stream")]
    assert len(search_calls) == 2
    assert len(download_calls) == 1


def test_pixabay_tries_next_ranked_candidate_after_candidate_specific_failure(tmp_path, monkeypatch):
    downloaded = []

    def fake_get(url, **kwargs):
        if not kwargs.get("stream"):
            return SearchResponse({"hits": [
                video_hit(31, "person typing keyboard laptop", "https://cdn.test/bad.mp4", likes=100),
                video_hit(32, "person typing keyboard laptop", "https://cdn.test/good.mp4", likes=1),
            ]})
        downloaded.append(url)
        if url.endswith("bad.mp4"):
            response = DownloadResponse()
            response.status_code = 404
            return response
        return DownloadResponse()

    monkeypatch.setattr(pixabay_media.requests, "get", fake_get)
    settings = SimpleNamespace(pixabay_api_key="test-key", cache_dir=tmp_path / "cache")

    result = pixabay_media.fetch_pixabay(settings, "person typing keyboard laptop", "video", tmp_path / "media")

    assert result is not None
    assert result["source_url"].endswith("test-32/")
    assert downloaded == ["https://cdn.test/bad.mp4", "https://cdn.test/good.mp4"]


def test_pixabay_429_is_not_retried_or_hidden(tmp_path, monkeypatch):
    calls = []

    class LimitedResponse(DownloadResponse):
        status_code = 429
        headers = {"Retry-After": "45"}

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        if not kwargs.get("stream"):
            return SearchResponse({"hits": [video_hit(41, "person typing keyboard", "https://cdn.test/limited.mp4")]})
        return LimitedResponse(headers={"Retry-After": "45"})

    monkeypatch.setattr(pixabay_media.requests, "get", fake_get)
    settings = SimpleNamespace(pixabay_api_key="test-key", cache_dir=tmp_path / "cache")

    with pytest.raises(pixabay_media.PixabayError) as exc:
        pixabay_media.fetch_pixabay(settings, "person typing keyboard", "video", tmp_path / "media")

    assert exc.value.is_rate_limited
    assert exc.value.retry_after == "45"
    assert len(calls) == 2  # one search, one CDN request; no alternate CDN attempts


def test_pixabay_search_429_is_propagated_with_retry_after(tmp_path, monkeypatch):
    class LimitedSearch(SearchResponse):
        status_code = 429
        headers = {"Retry-After": "60"}

    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        return LimitedSearch({"hits": []})

    monkeypatch.setattr(pixabay_media.requests, "get", fake_get)
    settings = SimpleNamespace(pixabay_api_key="test-key", cache_dir=tmp_path / "cache")

    with pytest.raises(pixabay_media.PixabayError) as exc:
        pixabay_media.fetch_pixabay(settings, "computer office", "photo", tmp_path / "media")

    assert exc.value.is_rate_limited
    assert exc.value.retry_after == "60"
    assert len(calls) == 1


def test_stock_asset_failure_never_falls_back_to_local_renderer(tmp_path, monkeypatch):
    warnings = []
    renderer_called = False

    def no_asset(*_args, **_kwargs):
        return None

    def forbidden_renderer(*_args, **_kwargs):
        nonlocal renderer_called
        renderer_called = True
        raise AssertionError("stock beat must not silently use the local renderer")

    monkeypatch.setattr(production_director, "fetch_pixabay", no_asset)
    monkeypatch.setattr(production_director, "render_motion_graphic", forbidden_renderer)

    settings = SimpleNamespace()
    scene = {"id": "s_001"}
    beat = {
        "asset_strategy": "stock",
        "visual_type": "photo",
        "search_queries": ["computer office"],
    }

    with pytest.raises(RuntimeError, match="локальная графика не подставлена"):
        production_director._asset_for_beat(settings, scene, beat, tmp_path, warnings, 1, 3.0)

    report = tmp_path / "s_001_01_asset_failure.json"
    assert report.is_file()
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["status"] == "manual_review_required"
    assert payload["requested_media_type"] == "photo"
    assert renderer_called is False


def test_stock_video_uses_photo_only_when_no_video_candidate_exists(tmp_path, monkeypatch):
    calls = []

    def fake_fetch(_settings, _queries, kind, _destination):
        calls.append(kind)
        if kind == "video":
            return None
        image_path = tmp_path / "fallback.jpg"
        image_path.write_bytes(b"x" * 2048)
        return {
            "path": str(image_path),
            "media_type": "image",
            "source": "Pixabay",
            "source_url": "https://pixabay.com/photos/fallback/",
            "creator": "TestCreator",
            "license_name": "Pixabay Content License — human review required",
            "rights_status": "review_required",
        }

    monkeypatch.setattr(production_director, "fetch_pixabay", fake_fetch)
    monkeypatch.setattr(production_director, "_validate_pixabay_asset", lambda *_args: (True, "image_ok_1920x1080"))
    monkeypatch.setattr(production_director, "render_stock_overlay", lambda _texts, path: path)

    settings = SimpleNamespace()
    beat = {"asset_strategy": "stock", "visual_type": "video", "search_queries": ["typing laptop"]}
    result = production_director._asset_for_beat(
        settings, {"id": "s_002"}, beat, tmp_path, [], 1, 3.0
    )

    assert calls == ["video", "photo"]
    assert result["selection_fallback"] == "video_to_photo"
    assert result["requested_media_type"] == "video"
