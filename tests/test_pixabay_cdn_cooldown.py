from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from video_farm import pixabay_media as pixabay


class _Response:
    def __init__(self, status_code: int, headers: dict[str, str] | None = None):
        self.status_code = status_code
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def iter_content(self, _chunk_size):
        yield b"x" * 2048


def test_retry_after_delta_seconds_is_parsed():
    assert pixabay._retry_after_delay("45", now=1000.0) == 45.0


def test_retry_after_http_date_is_parsed():
    from email.utils import formatdate
    target = 1120.0
    header = formatdate(target, usegmt=True)
    assert pixabay._retry_after_delay(header, now=1000.0) == 120.0


def test_cdn_429_persists_cooldown_and_blocks_future_downloads(tmp_path, monkeypatch):
    state_file = tmp_path / "cdn_cooldown.json"
    monkeypatch.setattr(pixabay, "PIXABAY_CDN_COOLDOWN_FILE", state_file)
    monkeypatch.setattr(pixabay.requests, "get", lambda *_a, **_k: _Response(429, {"Retry-After": "300"}))

    with pytest.raises(pixabay.PixabayError) as first:
        pixabay._download_candidate("https://cdn.pixabay.com/video/test.mp4", tmp_path / "first.mp4", "secret")
    assert first.value.is_rate_limited
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert state["scope"] == "pixabay_cdn"
    assert state["retry_after_header"] == "300"
    assert state["cooldown_until_epoch"] > state["observed_at_epoch"]

    def unexpected_request(*_a, **_k):
        raise AssertionError("A request must not be sent during the persisted CDN cooldown")

    monkeypatch.setattr(pixabay.requests, "get", unexpected_request)
    with pytest.raises(pixabay.PixabayError, match="на паузе") as second:
        pixabay._download_candidate("https://cdn.pixabay.com/video/another.mp4", tmp_path / "second.mp4", "secret")
    assert second.value.is_rate_limited


def test_existing_local_asset_is_reused_during_cooldown(tmp_path, monkeypatch):
    state_file = tmp_path / "cdn_cooldown.json"
    monkeypatch.setattr(pixabay, "PIXABAY_CDN_COOLDOWN_FILE", state_file)
    pixabay._persist_cdn_cooldown("300", now=1000.0)
    monkeypatch.setattr(pixabay.time, "time", lambda: 1001.0)
    existing = tmp_path / "already_downloaded.jpg"
    existing.write_bytes(b"x" * 2048)

    def unexpected_request(*_a, **_k):
        raise AssertionError("Existing valid file must be reused without network access")

    monkeypatch.setattr(pixabay.requests, "get", unexpected_request)
    pixabay._download_candidate("https://cdn.pixabay.com/photo/existing.jpg", existing, "secret")
    assert existing.stat().st_size == 2048


def test_urllib3_debug_log_redacts_pixabay_api_key(caplog):
    logger = logging.getLogger("urllib3.connectionpool")
    with caplog.at_level(logging.DEBUG, logger="urllib3.connectionpool"):
        logger.debug('GET /api/?key=real-secret-token&q=test HTTP/1.1')
    assert "real-secret-token" not in caplog.text
    assert "key=[REDACTED]" in caplog.text
