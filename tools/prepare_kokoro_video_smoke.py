from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SCRIPT = ROOT / "data" / "kokoro_stress_audio_test_script.json"
OUT_DIR = ROOT / "output" / "kokoro-production-video-smoke"

EXPECTED_IDS = ["door_lock", "old_castle", "door_lock_genitive"]


def main() -> int:
    if not SOURCE_SCRIPT.is_file():
        raise FileNotFoundError(f"Не найден исходный аудиосценарий: {SOURCE_SCRIPT}")

    source = json.loads(SOURCE_SCRIPT.read_text(encoding="utf-8"))
    blocks = source.get("blocks")
    if not isinstance(blocks, list):
        raise ValueError("В исходном сценарии поле blocks должно быть списком.")

    actual_ids = [str(block.get("id") or "") for block in blocks if isinstance(block, dict)]
    if len(actual_ids) != len(blocks) or actual_ids != EXPECTED_IDS:
        raise ValueError(
            "Исходный сценарий отличается от ожидаемого smoke fixture. "
            f"Ожидались ID {EXPECTED_IDS}, получены {actual_ids}."
        )

    prepared = dict(source)
    prepared["title"] = "Kokoro-ru v2 — короткий production video smoke test"
    prepared["topic"] = "Проверка сквозного конвейера Kokoro → PNG → MP4"
    prepared_blocks = []

    for block in blocks:
        voice_text = str(block.get("voice_text") or "").strip()
        if not voice_text:
            raise ValueError(f"Пустой voice_text в блоке {block['id']}.")
        item = dict(block)
        item["slides"] = [
            {
                "type": "quote",
                "title": str(block.get("heading") or block["id"]),
                "body": voice_text,
            }
        ]
        prepared_blocks.append(item)

    prepared["blocks"] = prepared_blocks
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    script_path = OUT_DIR / "script.json"
    assets_path = OUT_DIR / "assets_manifest.json"

    script_path.write_text(
        json.dumps(prepared, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    assets_path.write_text(
        json.dumps({"broll": [], "images": []}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("Prepared short-video smoke inputs.")
    print(f"Source fixture (unchanged): {SOURCE_SCRIPT}")
    print(f"Prepared script: {script_path}")
    print(f"Empty assets manifest: {assets_path}")
    print(f"Blocks: {len(prepared_blocks)}; slides: {sum(len(b['slides']) for b in prepared_blocks)}")
    print("Existing Kokoro WAV/manifest output is not modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
