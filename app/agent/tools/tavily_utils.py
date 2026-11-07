from __future__ import annotations

import asyncio
import re

from app.errors import ToolError

REQUEST_TIMEOUT = 15.0
MAX_ATTEMPTS = 2

CNY_MARKERS = ("元", "¥", "￥", "人民币")
CNY_LATIN_MARKERS = ("rmb", "cny", "yuan")


async def search_with_retry(
    client,
    query: str,
    max_results: int,
    timeout: float = REQUEST_TIMEOUT,
    attempts: int = MAX_ATTEMPTS,
    **search_kwargs,
) -> dict:
    params = {
        "search_depth": "advanced",
        "include_answer": True,
        "max_results": max_results,
    }
    params.update(search_kwargs)

    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(client.search, query, **params),
                timeout=timeout,
            )
        except Exception as exc:  # noqa: BLE001 - 工具边界统一转类型化错误
            last_error = exc
    raise ToolError(
        "tavily_unavailable",
        f"Tavily 查询失败（已重试 {attempts - 1} 次）：{last_error}",
    )


def text_of(payload: dict) -> str:
    parts = [payload.get("answer", "")]
    for item in payload.get("results") or []:
        parts.append(item.get("title", ""))
        parts.append(item.get("content", ""))
    return "\n".join(part for part in parts if part)


def urls_of(payload: dict) -> set[str]:
    return {
        item.get("url", "")
        for item in payload.get("results") or []
        if item.get("url")
    }


def contains_number(text: str, value: float) -> bool:
    pattern = r"(?<![\d.])" + re.escape(f"{value:g}") + r"(?![\d.])"
    return re.search(pattern, text) is not None


def is_cny_evidence(text: str) -> bool:
    if any(marker in text for marker in CNY_MARKERS):
        return True
    lowered = text.lower()
    return any(marker in lowered for marker in CNY_LATIN_MARKERS)


_CNY_PRICE_PATTERNS = (
    re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)\s*(?:元|人民币)"),
    re.compile(r"(?:¥|￥)\s*(\d+(?:\.\d+)?)"),
    re.compile(
        r"(?<![\d.])(\d+(?:\.\d+)?)\s*(?:yuan|rmb|cny)",
        re.IGNORECASE,
    ),
)

_CNY_RANGE_PATTERNS = (
    re.compile(
        r"(?<![\d.])(\d+(?:\.\d+)?)\s*[-–—~至]\s*(\d+(?:\.\d+)?)\s*(?:元|人民币)"
    ),
    re.compile(
        r"(?:¥|￥)\s*(\d+(?:\.\d+)?)\s*[-–—~至]\s*(\d+(?:\.\d+)?)"
    ),
    re.compile(
        r"(?<![\d.])(\d+(?:\.\d+)?)\s*[-–—~至]\s*(\d+(?:\.\d+)?)\s*(?:yuan|rmb|cny)",
        re.IGNORECASE,
    ),
)


def contains_cny_price(text: str, value: float) -> bool:
    for pattern in _CNY_PRICE_PATTERNS:
        for match in pattern.finditer(text):
            try:
                found = float(match.group(1))
            except (TypeError, ValueError):
                continue
            if abs(found - value) < 1e-6:
                return True

    for pattern in _CNY_RANGE_PATTERNS:
        for match in pattern.finditer(text):
            try:
                low = float(match.group(1))
                high = float(match.group(2))
            except (TypeError, ValueError):
                continue
            if abs(low - value) < 1e-6 or abs(high - value) < 1e-6:
                return True
    return False
