#!/usr/bin/env python3
"""One-shot diagnostic for MWS GPT Model Hub image generation.

The script deliberately sends at most one generation request. It does not
modify .env, project settings, or the production pipeline.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

DEFAULT_MODEL = "gemini-3.1-flash-image"
DEFAULT_PROMPT = (
    "Create one cinematic, professional 16:9 editorial image for a Russian-language "
    "science documentary about AI hallucinations. Show a close-up of a translucent "
    "neural network made of luminous connected nodes, with one bright but misleading "
    "path branching away from the verified network. Deep navy and charcoal palette, "
    "subtle warm accent, realistic volumetric light, strong composition, detailed, "
    "visually clear at 1920x1080. Absolutely no text, letters, numbers, logos, watermarks, "
    "UI panels, borders, collage, slide layout, or infographic labels. A single coherent scene."
)


@dataclass
class ProbeConfig:
    base_url: str
    api_key: str
    model: str
    prompt: str
    endpoint: str
    endpoint_url: str | None
    timeout: int
    output_dir: Path


def read_env_file(path: Path) -> dict[str, str]:
    """Read simple KEY=VALUE .env lines without evaluating shell syntax."""
    result: dict[str, str] = {}
    if not path.is_file():
        return result
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        # A trailing comment is stripped only when separated by whitespace.
        value = re.split(r"\s+#", value, maxsplit=1)[0].rstrip()
        if key:
            result[key] = value
    return result


def _safe_text(value: str, secret: str) -> str:
    value = value.replace(secret, "[REDACTED]") if secret else value
    value = re.sub(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s\"']+", r"\1[REDACTED]", value)
    return value


def _decode_data_uri(value: str) -> tuple[bytes, str] | None:
    match = re.match(r"^data:image/(png|jpeg|jpg|webp);base64,(.+)$", value, re.I | re.S)
    if not match:
        return None
    subtype, encoded = match.groups()
    try:
        payload = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        return None
    ext = "jpg" if subtype.lower() in {"jpeg", "jpg"} else subtype.lower()
    return payload, ext


def _decode_b64(value: str) -> tuple[bytes, str] | None:
    if not isinstance(value, str) or not value.strip():
        return None
    data_uri = _decode_data_uri(value.strip())
    if data_uri:
        return data_uri
    try:
        raw = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        return None
    return raw, "png"


def extract_inline_image(payload: dict[str, Any]) -> tuple[bytes, str] | None:
    """Extract common OpenAI/Gemini image-output shapes; no network access."""
    data = payload.get("data")
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            for key in ("b64_json", "image_base64", "base64", "data"):
                value = item.get(key)
                if isinstance(value, str):
                    decoded = _decode_b64(value)
                    if decoded:
                        return decoded

    choices = payload.get("choices")
    if isinstance(choices, list):
        for choice in choices:
            message = choice.get("message", {}) if isinstance(choice, dict) else {}
            content = message.get("content") if isinstance(message, dict) else None
            if isinstance(content, list):
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    for key in ("b64_json", "image_base64", "base64", "data"):
                        value = part.get(key)
                        if isinstance(value, str):
                            decoded = _decode_b64(value)
                            if decoded:
                                return decoded
                    image_url = part.get("image_url")
                    if isinstance(image_url, dict):
                        decoded = _decode_data_uri(str(image_url.get("url", "")))
                        if decoded:
                            return decoded
                    elif isinstance(image_url, str):
                        decoded = _decode_data_uri(image_url)
                        if decoded:
                            return decoded

    # Gemini generateContent-like output.
    candidates = payload.get("candidates")
    if isinstance(candidates, list):
        for candidate in candidates:
            content = candidate.get("content", {}) if isinstance(candidate, dict) else {}
            parts = content.get("parts", []) if isinstance(content, dict) else []
            if isinstance(parts, list):
                for part in parts:
                    if not isinstance(part, dict):
                        continue
                    inline = part.get("inlineData") or part.get("inline_data")
                    if isinstance(inline, dict):
                        decoded = _decode_b64(str(inline.get("data", "")))
                        if decoded:
                            mime = str(inline.get("mimeType") or inline.get("mime_type") or "image/png")
                            ext = "jpg" if "jpeg" in mime else "webp" if "webp" in mime else "png"
                            return decoded[0], ext
    return None


def find_image_url(payload: dict[str, Any]) -> str | None:
    data = payload.get("data")
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and isinstance(item.get("url"), str):
                return item["url"]
    return None


def validate_image_bytes(raw: bytes) -> tuple[bool, str, int, int]:
    try:
        from PIL import Image
        with Image.open(BytesIO(raw)) as im:
            im.verify()
        with Image.open(BytesIO(raw)) as im:
            width, height = im.size
            fmt = (im.format or "unknown").upper()
        if width < 640 or height < 360:
            return False, f"image_too_small:{fmt}", width, height
        return True, fmt, width, height
    except Exception as exc:  # Pillow reports multiple format-specific errors.
        return False, f"invalid_image:{type(exc).__name__}", 0, 0


def _download_https(url: str, timeout: int) -> bytes:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Image URL must be an HTTPS URL")
    if parsed.username or parsed.password:
        raise ValueError("Image URL must not contain credentials")
    req = urllib.request.Request(url, headers={"User-Agent": "AI-Video-Factory-RU-MWS-Probe/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"Image download returned HTTP {response.status}")
        content_type = response.headers.get("Content-Type", "")
        if not content_type.lower().startswith("image/"):
            raise RuntimeError(f"Image URL returned unexpected Content-Type: {content_type}")
        data = response.read(30 * 1024 * 1024 + 1)
        if len(data) > 30 * 1024 * 1024:
            raise RuntimeError("Image exceeds 30 MB safety limit")
        return data


def build_config(args: argparse.Namespace) -> ProbeConfig:
    env_file = read_env_file(Path(args.env_file))
    def get_env(key: str, default: str = "") -> str:
        return os.environ.get(key, env_file.get(key, default))

    base_url = args.base_url or get_env("LLM_PRIMARY_BASE_URL") or get_env("MWS_BASE_URL")
    api_key = args.api_key or get_env("LLM_PRIMARY_API_KEY") or get_env("MWS_API_KEY")
    if not base_url:
        raise ValueError("MWS base URL not found. Set LLM_PRIMARY_BASE_URL in .env or pass --base-url.")
    if not api_key:
        raise ValueError("MWS API key not found. Set LLM_PRIMARY_API_KEY in .env or pass --api-key.")
    if not base_url.lower().startswith("https://"):
        raise ValueError("MWS base URL must use HTTPS")
    base_url = base_url.rstrip("/")
    endpoint = args.endpoint.strip("/")
    return ProbeConfig(
        base_url=base_url,
        api_key=api_key,
        model=args.model,
        prompt=args.prompt,
        endpoint=endpoint,
        endpoint_url=args.endpoint_url,
        timeout=args.timeout,
        output_dir=Path(args.out),
    )


def run_probe(cfg: ProbeConfig) -> dict[str, Any]:
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    url = cfg.endpoint_url or f"{cfg.base_url}/{cfg.endpoint}"
    if not url.lower().startswith("https://"):
        raise ValueError("Image generation endpoint must use HTTPS")
    body: dict[str, Any] = {"model": cfg.model, "prompt": cfg.prompt, "n": 1}
    request_bytes = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=request_bytes,
        method="POST",
        headers={
            "Authorization": f"Bearer {cfg.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "AI-Video-Factory-RU-MWS-Probe/1.0",
        },
    )
    started = time.perf_counter()
    status_code: int | None = None
    response_body = b""
    headers: dict[str, str] = {}
    error: str | None = None
    try:
        with urllib.request.urlopen(req, timeout=cfg.timeout) as response:
            status_code = response.status
            headers = {k: v for k, v in response.headers.items() if k.lower() in {
                "content-type", "x-request-id", "request-id", "x-ratelimit-remaining-requests"
            }}
            response_body = response.read(40 * 1024 * 1024 + 1)
            if len(response_body) > 40 * 1024 * 1024:
                raise RuntimeError("API response exceeds 40 MB safety limit")
    except urllib.error.HTTPError as exc:
        status_code = exc.code
        headers = {k: v for k, v in exc.headers.items() if k.lower() in {"content-type", "x-request-id", "request-id"}}
        response_body = exc.read(2 * 1024 * 1024)
        error = f"HTTP {exc.code}: {exc.reason}"
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    elapsed = round(time.perf_counter() - started, 3)

    raw_text = response_body.decode("utf-8", errors="replace")
    safe_text = _safe_text(raw_text[:200_000], cfg.api_key)
    response_path = cfg.output_dir / "response_sanitized.json.txt"
    response_path.write_text(safe_text, encoding="utf-8")

    report: dict[str, Any] = {
        "probe_version": "1.0.0",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "model": cfg.model,
        "endpoint": url,
        "request": {"n": 1, "prompt_chars": len(cfg.prompt), "size_parameter": "not sent; avoid unsupported assumptions"},
        "http_status": status_code,
        "elapsed_seconds": elapsed,
        "response_headers": headers,
        "response_bytes": len(response_body),
        "result": "api_error" if error else "unparsed_response",
        "error": _safe_text(error, cfg.api_key) if error else None,
        "image": None,
        "notes": [
            "This probe tests POST /images/generations as an OpenAI-compatible endpoint hypothesis.",
            "MWS public documentation confirms image output capability for this proxy model but does not clearly document the image-generation route.",
            "At most one generation request is sent; the script does not retry automatically.",
        ],
    }

    if status_code is not None and 200 <= status_code < 300:
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError:
            payload = {}
            report["result"] = "unexpected_non_json_response"
        image_data = extract_inline_image(payload) if isinstance(payload, dict) else None
        image_url = find_image_url(payload) if isinstance(payload, dict) else None
        if image_data:
            image_bytes, ext = image_data
        elif image_url:
            try:
                image_bytes = _download_https(image_url, cfg.timeout)
                ext = "png"
            except Exception as exc:
                image_bytes = b""
                ext = "png"
                report["error"] = f"Image URL download failed: {type(exc).__name__}: {exc}"
        else:
            image_bytes, ext = b"", "png"

        if image_bytes:
            ok, fmt, width, height = validate_image_bytes(image_bytes)
            if ok:
                actual_ext = "jpg" if fmt in {"JPEG", "JPG"} else "webp" if fmt == "WEBP" else "png"
                image_path = cfg.output_dir / f"generated_image.{actual_ext}"
                image_path.write_bytes(image_bytes)
                report["result"] = "image_generated_and_validated"
                report["image"] = {"path": str(image_path), "format": fmt, "width": width,
                                   "height": height, "bytes": len(image_bytes)}
            else:
                report["result"] = "image_payload_invalid"
                report["image"] = {"validation": fmt, "width": width, "height": height,
                                   "bytes": len(image_bytes)}
        else:
            report["result"] = "http_ok_but_no_recognized_image_payload"
            # Keep response structure summary, not full base64 / URL payload.
            report["response_top_level_keys"] = sorted(payload.keys()) if isinstance(payload, dict) else []
            if isinstance(payload, dict):
                report["response_object"] = payload.get("object")
                report["response_model"] = payload.get("model")
                report["usage"] = payload.get("usage") or payload.get("usageMetadata")
                if isinstance(payload.get("data"), list):
                    report["data_item_keys"] = [sorted(x.keys()) for x in payload["data"] if isinstance(x, dict)][:3]
                if isinstance(payload.get("candidates"), list):
                    report["candidate_count"] = len(payload["candidates"])
    else:
        # The API error body is useful for identifying an unsupported route or payload.
        report["error_detail"] = safe_text[:6000]

    report_path = cfg.output_dir / "probe_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="One-request MWS Gemini image-generation compatibility probe")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--api-key", default=None, help="Avoid command-line use where shell history is shared")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--endpoint", default="images/generations", help="Relative endpoint below the configured MWS base URL")
    parser.add_argument("--endpoint-url", default=None, help="Override the full HTTPS endpoint URL if MWS support provides a different route")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--out", default="output/diagnostics/mws-gemini-image")
    args = parser.parse_args(argv)
    try:
        cfg = build_config(args)
        print(f"MWS image probe: model={cfg.model}")
        print(f"Endpoint: {cfg.base_url}/{cfg.endpoint}")
        print("Sending one image-generation request; no automatic retries.")
        report = run_probe(cfg)
        print(f"Result: {report['result']}")
        print(f"HTTP status: {report['http_status']}")
        print(f"Elapsed: {report['elapsed_seconds']} sec")
        print(f"Report: {cfg.output_dir / 'probe_report.json'}")
        if report.get("image") and report["image"].get("path"):
            print(f"Image: {report['image']['path']} ({report['image']['width']}x{report['image']['height']})")
        if report.get("error"):
            print(f"Error: {report['error']}")
        return 0 if report["result"] == "image_generated_and_validated" else 2
    except Exception as exc:
        print(f"Probe configuration/runtime error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
