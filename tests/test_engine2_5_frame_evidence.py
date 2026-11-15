from __future__ import annotations

import json
import shutil
import subprocess

import pytest
from PIL import Image

from video_farm.director_visuals import (
    _sample_times_for_slot,
    audit_final_video_frames,
)


def test_three_samples_are_inside_voice_interval_not_editorial_pause():
    slot = {
        "start_sec": 2.0,
        "voice_end_sec": 6.0,
        "end_sec": 6.12,
    }

    samples = _sample_times_for_slot(slot, 3)

    assert len(samples) == 3
    assert [round(position, 2) for _, position in samples] == [0.25, 0.5, 0.75]
    assert [round(timestamp, 2) for timestamp, _ in samples] == [3.0, 4.0, 5.0]
    assert all(2.0 < timestamp < 6.0 for timestamp, _ in samples)
    assert all(timestamp < slot["voice_end_sec"] for timestamp, _ in samples)


def test_single_sample_and_invalid_sample_counts():
    slot = {"start_sec": 0.0, "voice_end_sec": 2.0, "end_sec": 2.12}

    samples = _sample_times_for_slot(slot, 1)
    assert len(samples) == 1
    assert samples[0][0] == pytest.approx(1.0)

    for invalid in (0, 8, True, 1.5):
        with pytest.raises(ValueError):
            _sample_times_for_slot(slot, invalid)


def test_frame_evidence_records_hashes_provenance_and_cross_shot_repeats(tmp_path):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("FFmpeg is not installed")

    still = tmp_path / "still.png"
    Image.new("RGB", (640, 360), (40, 90, 140)).save(still)

    video = tmp_path / "final.mp4"
    subprocess.run(
        [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-loop", "1", "-i", str(still),
            "-t", "2.24", "-r", "25",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(video),
        ],
        check=True,
        capture_output=True,
    )

    timeline = [
        {
            "scene_id": "s_001",
            "beat_id": "b01",
            "shot_id": "b01_s01",
            "source_beat_id": "b01",
            "cut_reason": "Первый смысловой кадр",
            "start_sec": 0.0,
            "voice_end_sec": 1.0,
            "end_sec": 1.12,
            "spoken_text": "Первая фраза диктора.",
            "visual_path": "assets/first.mp4",
            "visual_source": "Pixabay",
            "source_url": "https://example.org/asset-one",
            "creator": "Example Creator",
            "license_name": "Pixabay Content License",
            "rights_status": "review_required",
            "sha256": "a" * 64,
        },
        {
            "scene_id": "s_001",
            "beat_id": "b02",
            "shot_id": "b01_s02",
            "source_beat_id": "b01",
            "cut_reason": "Второй смысловой кадр",
            "start_sec": 1.12,
            "voice_end_sec": 2.12,
            "end_sec": 2.24,
            "spoken_text": "Вторая фраза диктора.",
            "visual_path": "assets/second.mp4",
            "visual_source": "Pixabay",
            "source_url": "https://example.org/asset-two",
            "creator": "Another Creator",
            "license_name": "Pixabay Content License",
            "rights_status": "review_required",
            "sha256": "b" * 64,
        },
    ]

    report_path = tmp_path / "visual_audit.json"
    contact_path = tmp_path / "contact_sheet.jpg"

    report = audit_final_video_frames(
        video,
        timeline,
        report_path,
        contact_path,
        ffmpeg=ffmpeg,
        sample_count=3,
    )

    assert report["schema_version"] == "2.5-frame-evidence"
    assert report["sampled_frame_count"] == 6
    assert report["decoded_frame_count"] == 6
    assert report["semantic_verdict"] == "not_run"
    assert report["human_review_required"] is True
    assert len(report["video_sha256"]) == 64

    first_shot = report["entries"][:3]
    second_shot = report["entries"][3:]

    assert all(item["shot_id"] == "b01_s01" for item in first_shot)
    assert all(item["shot_id"] == "b01_s02" for item in second_shot)

    # The first spoken interval ends at 1.0 sec. Its 0.12 sec editorial pause
    # must not leak into the frame samples.
    assert all(item["sample_time_sec"] < 1.0 for item in first_shot)
    assert all(item["spoken_end_sec"] == 1.0 for item in first_shot)

    # Static frames within one shot are expected, not cross-shot repetition.
    assert all("duplicate_of" not in item for item in first_shot)

    # The same still is used by the second shot in this fixture, so cross-shot
    # duplicate detection must report it.
    assert any("duplicate_of" in item for item in second_shot)

    first_entry = first_shot[0]
    assert first_entry["source_url"] == "https://example.org/asset-one"
    assert first_entry["creator"] == "Example Creator"
    assert first_entry["license_name"] == "Pixabay Content License"
    assert first_entry["rights_status"] == "review_required"
    assert first_entry["asset_sha256"] == "a" * 64
    assert len(first_entry["sha256"]) == 64
    assert first_entry["dimensions"] == [640, 360]
    assert first_entry["spoken_text"] == "Первая фраза диктора."

    assert contact_path.is_file()
    assert json.loads(report_path.read_text(encoding="utf-8"))["sampled_frame_count"] == 6
