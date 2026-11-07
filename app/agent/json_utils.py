from __future__ import annotations

import json
from typing import Any


def _clean(text: str) -> str:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned[:4].lower() == "json":
            cleaned = cleaned[4:].strip()
    return cleaned


def parse_json_object(text: str) -> dict[str, Any] | None:
    cleaned = _clean(text)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        payload = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def parse_json_array(text: str) -> list[Any] | None:
    cleaned = _clean(text)
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start == -1 or end <= start:
        return None
    try:
        payload = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, list) else None
