from __future__ import annotations
# Set cache locations before importing torch (important for Windows profiles with Cyrillic names).
import hashlib
import importlib.metadata
import json
import logging
import math
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import Settings
from .common import ensure_dir, read_json, write_json
from .text_normalization import (
    NORMALIZER_VERSION, find_numeric_tokens, normalizer_backend, normalize_for_speech,
)

log = logging.getLogger(__name__)

def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _wav_info(path: Path) -> dict[str, Any]:
    try:
        with wave.open(str(path), "rb") as w:
            info = {
                "sample_rate": w.getframerate(),
                "channels": w.getnchannels(),
                "sample_width_bytes": w.getsampwidth(),
                "frames": w.getnframes(),
            }
    except (wave.Error, OSError) as exc:
        raise RuntimeError(f"Созданный WAV повреждён или имеет неподдерживаемый формат: {path}") from exc
    if info["sample_rate"] <= 0 or info["channels"] <= 0 or info["frames"] <= 0:
        raise RuntimeError(f"Созданный WAV пустой или имеет некорректные параметры: {path}")
    info["duration_seconds"] = round(info["frames"] / info["sample_rate"], 3)
    return info


def _piper_package_version() -> str | None:
    try:
        return importlib.metadata.version("piper-tts")
    except importlib.metadata.PackageNotFoundError:
        return None


def _resolve_model_urls(voice: str) -> tuple[str, str]:
    model_override = os.getenv("TTS_MODEL_URL", "").strip()
    config_override = os.getenv("TTS_CONFIG_URL", "").strip()
    if model_override or config_override:
        if not (model_override and config_override):
            raise RuntimeError("TTS_MODEL_URL и TTS_CONFIG_URL нужно задавать вместе.")
        return model_override, config_override
    if voice != "ru_RU-dmitri-medium":
        raise RuntimeError(
            f"Для голоса {voice!r} не задана пара TTS_MODEL_URL и TTS_CONFIG_URL. "
            "Не скачиваю модель Дмитрия под именем другого голоса."
        )
    base_url = os.getenv(
        "TTS_MODEL_BASE_URL",
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/ru/ru_RU/dmitri/medium",
    ).rstrip("/")
    return (
        f"{base_url}/ru_RU-dmitri-medium.onnx",
        f"{base_url}/ru_RU-dmitri-medium.onnx.json",
    )


def _download_file(url: str, target: Path) -> None:
    import requests
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.stat().st_size > 1024:
        return
    tmp = target.with_suffix(target.suffix + ".part")
    try:
        with requests.get(url, stream=True, timeout=(20, 180), headers={"User-Agent": "video-farm/0.1"}) as r:
            r.raise_for_status()
            with tmp.open("wb") as f:
                for chunk in r.iter_content(1024 * 256):
                    if chunk:
                        f.write(chunk)
        if tmp.stat().st_size < 1024:
            raise RuntimeError("Загруженный файл слишком мал; возможно, сервер вернул страницу ошибки.")
        tmp.replace(target)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def _duration(path: Path) -> float:
    return float(_wav_info(path)["duration_seconds"])


def synthesize(settings: Settings, script_path: Path, out_dir: Path, *, speed: float | None = None) -> dict[str, Any]:
    script = read_json(script_path)
    blocks = script.get("blocks", [])
    if not isinstance(blocks, list) or not blocks:
        raise ValueError("В сценарии нет блоков")

    speed = settings.tts_speed if speed is None else speed
    if not math.isfinite(float(speed)) or not 0.5 <= float(speed) <= 2.0:
        raise ValueError("Скорость TTS должна быть в диапазоне от 0.5 до 2.0.")
    speed = float(speed)
    if settings.tts_engine.lower() != "piper":
        raise RuntimeError(
            f"Неизвестный TTS_ENGINE={settings.tts_engine!r}. Для этой ветки выбран Piper; "
            "не переключайте модель без проверки лицензии."
        )

    # Fail before spending CPU/network time if even one block is malformed.
    prepared: list[tuple[str, dict[str, Any], str, str]] = []
    seen_ids: set[str] = set()
    for i, block in enumerate(blocks, 1):
        if not isinstance(block, dict):
            raise ValueError(f"Блок сценария №{i} должен быть JSON-объектом.")
        block_id = str(block.get("id") or f"block_{i}")
        if block_id in seen_ids:
            raise ValueError(f"Повторяется ID блока сценария: {block_id!r}.")
        seen_ids.add(block_id)
        source_text = str(block.get("voice_text", "")).strip()
        text = normalize_for_speech(source_text)
        if not text:
            raise ValueError(f"Пустой voice_text в блоке {block_id!r}; каждый блок должен иметь озвучку.")
        prepared.append((block_id, block, source_text, text))

    voice = str(settings.tts_speaker or "ru_RU-dmitri-medium").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", voice):
        raise ValueError("TTS_SPEAKER содержит недопустимые символы.")
    exe = shutil.which("piper")
    if not exe:
        candidate = Path(sys.executable).parent / ("piper.exe" if os.name == "nt" else "piper")
        if candidate.exists():
            exe = str(candidate)
    if not exe:
        # Some installations expose only the module entry point.
        try:
            __import__("piper")
            exe = "__python_module__"
        except Exception as exc:
            raise RuntimeError("Piper не найден. Установите его командой `pip install -e .[tts]` внутри .venv.") from exc

    model_dir = settings.data_dir / "models" / "piper"
    model_dir.mkdir(parents=True, exist_ok=True)
    model = model_dir / f"{voice}.onnx"
    config = model_dir / f"{voice}.onnx.json"
    model_url, config_url = _resolve_model_urls(voice)
    if not model.exists() or model.stat().st_size < 1024:
        log.info("Скачиваю модель TTS: %s", model_url)
        _download_file(model_url, model)
    if not config.exists() or config.stat().st_size < 100:
        log.info("Скачиваю конфигурацию голоса: %s", config_url)
        _download_file(config_url, config)
    try:
        voice_cfg = json.loads(config.read_text(encoding="utf-8"))
        sample_rate = int(voice_cfg.get("audio", {}).get("sample_rate", 22050))
    except Exception as exc:
        raise RuntimeError(f"Конфигурация Piper повреждена: {config}") from exc
    if sample_rate <= 0:
        raise RuntimeError(f"В конфигурации Piper некорректная частота дискретизации: {config}")

    out_dir = ensure_dir(out_dir)
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    overall_started = time.perf_counter()
    manifest: dict[str, Any] = {
        "status": "running",
        "generated_at_utc": started_at,
        "engine": "Piper TTS (CPU)",
        "engine_package": "piper-tts",
        "engine_version": _piper_package_version(),
        "engine_executable": "python -m piper" if exe == "__python_module__" else str(exe),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "voice": voice,
        "voice_gender": "male" if voice == "ru_RU-dmitri-medium" else None,
        "speed": speed,
        "text_normalizer_version": NORMALIZER_VERSION,
        "text_normalizer_backend": normalizer_backend(),
        "configured_sample_rate": sample_rate,
        # Piper is a Python console-script executable on this Windows setup.
        # Force UTF-8 in the child so stdin text is not decoded using the Windows ANSI code page.
        "stdin_encoding": "UTF-8",
        "child_python_utf8_mode": True,
        "quality_warnings": [],
        "model_file": str(model),
        "model_size_bytes": model.stat().st_size,
        "model_sha256": _sha256_file(model),
        "model_url": model_url,
        "config_file": str(config),
        "config_size_bytes": config.stat().st_size,
        "config_sha256": _sha256_file(config),
        "config_url": config_url,
        "voice_dataset_license": "CC0 (as listed in the Piper dmitri model card; re-check before commercial publication)" if voice == "ru_RU-dmitri-medium" else "NOT_VERIFIED",
        "model_card_url": "https://huggingface.co/rhasspy/piper-voices/blob/main/ru/ru_RU/dmitri/medium/MODEL_CARD" if voice == "ru_RU-dmitri-medium" else None,
        "blocks_expected": len(prepared),
        "blocks": [],
        "total_duration_seconds": 0.0,
        "elapsed_seconds": None,
    }
    for block_id, _block, _source_text, normalized_text in prepared:
        leftovers = find_numeric_tokens(normalized_text)
        if leftovers:
            warning = (
                f"Блок {block_id!r}: после нормализации остались числовые токены {leftovers}; "
                "проверьте произносимый текст вручную."
            )
            manifest["quality_warnings"].append(warning)
            log.warning(warning)

    manifest_path = out_dir / "manifest.json"
    write_json(manifest_path, manifest)

    try:
        for i, (block_id, block, source_text, text) in enumerate(prepared, 1):
            safe_block_id = re.sub(r"[^A-Za-z0-9_-]+", "_", block_id).strip("_") or f"block_{i}"
            dst = out_dir / f"{i:02d}_{safe_block_id}.wav"
            tmp_dst = dst.with_name(dst.stem + ".raw.wav")
            cmd = (
                [sys.executable, "-m", "piper", "--model", str(model), "--output_file", str(tmp_dst)]
                if exe == "__python_module__"
                else [exe, "--model", str(model), "--output_file", str(tmp_dst)]
            )
            block_started = time.perf_counter()
            # `piper.exe` is a Python console entry point. On Windows, the child
            # interpreter may otherwise decode piped UTF-8 bytes with the system
            # ANSI code page (e.g. cp1251/cp1252), producing unintelligible speech.
            # `encoding="utf-8"` controls only the parent side; these environment
            # variables configure text decoding inside the child process as well.
            piper_env = os.environ.copy()
            piper_env["PYTHONUTF8"] = "1"
            piper_env["PYTHONIOENCODING"] = "utf-8"
            try:
                subprocess.run(
                    cmd, input=text, check=True, capture_output=True, text=True,
                    encoding="utf-8", errors="strict", env=piper_env,
                )
            except subprocess.CalledProcessError as exc:
                raise RuntimeError(
                    "Piper не смог синтезировать блок " + block_id + ": " + (exc.stderr or "")[-1600:]
                ) from exc
            if not tmp_dst.exists() or tmp_dst.stat().st_size < 44:
                raise RuntimeError("Piper завершился, но WAV не создан: " + str(tmp_dst))
            _wav_info(tmp_dst)  # Check the Piper output before optional tempo conversion.
            if abs(speed - 1.0) > 0.001:
                cmd = [settings.ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(tmp_dst),
                       "-filter:a", f"atempo={speed:.6f}", "-acodec", "pcm_s16le", str(dst)]
                try:
                    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                    if not dst.exists() or dst.stat().st_size < 44:
                        raise RuntimeError("FFmpeg завершился без корректного выходного WAV.")
                except Exception as exc:
                    raise RuntimeError(f"Не удалось применить скорость {speed} к блоку {block_id}; исходный темп не подставлен молча.") from exc
                finally:
                    tmp_dst.unlink(missing_ok=True)
            else:
                tmp_dst.replace(dst)

            info = _wav_info(dst)
            if abs(info["sample_rate"] - sample_rate) > 1:
                raise RuntimeError(
                    f"Блок {block_id}: частота WAV ({info['sample_rate']}) не совпадает с конфигурацией голоса ({sample_rate})."
                )
            elapsed = round(time.perf_counter() - block_started, 3)
            word_count = len(re.findall(r"\b[\wЁёА-Яа-я]+\b", text))
            seconds_per_word = round(info["duration_seconds"] / max(word_count, 1), 3)
            if word_count >= 5 and seconds_per_word > 1.5:
                warning = (
                    f"Блок {block_id!r}: {seconds_per_word:.2f} сек./слово — необычно медленно; "
                    "проверьте WAV на слух и убедитесь, что Piper правильно декодировал русский текст."
                )
                manifest["quality_warnings"].append(warning)
                log.warning(warning)
            block_manifest = {
                "id": block_id,
                "heading": block.get("heading", ""),
                "file": dst.name,
                "duration_seconds": info["duration_seconds"],
                "seconds_per_word": seconds_per_word,
                "sample_rate": info["sample_rate"],
                "channels": info["channels"],
                "sample_width_bytes": info["sample_width_bytes"],
                "frames": info["frames"],
                "word_count": word_count,
                "source_voice_text": source_text,
                "normalized_voice_text": text,
                "source_voice_text_sha256": hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
                "normalized_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "unconverted_numeric_tokens": find_numeric_tokens(text),
                "elapsed_seconds": elapsed,
            }
            manifest["blocks"].append(block_manifest)
            manifest["total_duration_seconds"] = round(
                sum(float(x["duration_seconds"]) for x in manifest["blocks"]), 3
            )
            manifest["elapsed_seconds"] = round(time.perf_counter() - overall_started, 3)
            write_json(manifest_path, manifest)  # Preserve partial evidence if a later block fails.
            log.info("Озвучен блок %s: %.1f сек.; синтез занял %.1f сек.", block_id, info["duration_seconds"], elapsed)

        expected_ids = [item[0] for item in prepared]
        actual_ids = [item["id"] for item in manifest["blocks"]]
        if actual_ids != expected_ids:
            raise RuntimeError("Внутренняя ошибка: манифест озвучки не соответствует порядку блоков сценария.")
        manifest["status"] = "complete"
        manifest["elapsed_seconds"] = round(time.perf_counter() - overall_started, 3)
        write_json(manifest_path, manifest)
        return manifest
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        manifest["elapsed_seconds"] = round(time.perf_counter() - overall_started, 3)
        write_json(manifest_path, manifest)
        raise
