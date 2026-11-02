from __future__ import annotations
import json, re, hashlib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p

def write_json(path: str | Path, payload: Any) -> None:
    p = Path(path)
    ensure_dir(p.parent)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))

def words(text: str) -> list[str]:
    return re.findall(r"[A-Za-zА-Яа-яЁё0-9]+(?:[.-][A-Za-zА-Яа-яЁё0-9]+)*", text or "")

def word_count(text: str) -> int:
    return len(words(text))

def slugify(text: str, max_length: int = 60) -> str:
    s = re.sub(r"[^0-9A-Za-zА-Яа-яЁё]+", "-", (text or "").lower()).strip("-")
    return (s[:max_length].strip("-") or "video")

def stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

def parse_json_response(text: str) -> Any:
    """Parse valid JSON even if a provider wraps it in a Markdown code fence."""
    raw = (text or "").strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.I)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start_obj, end_obj = raw.find("{"), raw.rfind("}")
        start_arr, end_arr = raw.find("["), raw.rfind("]")
        if start_obj >= 0 and end_obj > start_obj:
            return json.loads(raw[start_obj:end_obj + 1])
        if start_arr >= 0 and end_arr > start_arr:
            return json.loads(raw[start_arr:end_arr + 1])
        raise
