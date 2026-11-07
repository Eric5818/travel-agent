from __future__ import annotations

import asyncio
import os

from app.errors import ToolError
from app.schemas import Attraction

REQUEST_TIMEOUT = 15.0
MAX_ATTEMPTS = 2


def _build_query(city: str, keywords: list[str]) -> str:
    joined = " ".join(keyword for keyword in keywords if keyword)
    parts = [city, joined, "景点 攻略 推荐"]
    return " ".join(part for part in parts if part)


async def _search_once(client, query: str, limit: int) -> dict:
    return await asyncio.wait_for(
        asyncio.to_thread(
            client.search,
            query,
            search_depth="advanced",
            include_answer=True,
            max_results=limit,
        ),
        timeout=REQUEST_TIMEOUT,
    )


def _to_attractions(payload: dict, keywords: list[str], limit: int) -> list[Attraction]:
    category = keywords[0] if keywords else "景点"
    results = payload.get("results") or []
    return [
        Attraction(
            name=raw.get("title", "").strip(),
            category=category,
            description=raw.get("content", "").strip(),
            address=None,
            source_url=raw.get("url", ""),
        )
        for raw in results[:limit]
        if raw.get("title")
    ]


async def search_attractions(
    city: str,
    keywords: list[str],
    limit: int = 8,
    api_key: str | None = None,
    client=None,
) -> list[Attraction]:
    if client is None:
        key = (api_key or os.environ.get("TAVILY_API_KEY", "")).strip()
        if not key:
            raise ToolError(
                "tavily_not_configured",
                "未配置 TAVILY_API_KEY，无法搜索景点",
            )
        from tavily import TavilyClient

        client = TavilyClient(api_key=key)

    query = _build_query(city, keywords)
    last_error: Exception | None = None

    for _ in range(MAX_ATTEMPTS):
        try:
            payload = await _search_once(client, query, limit)
            return _to_attractions(payload, keywords, limit)
        except Exception as exc:  # noqa: BLE001 - 工具边界统一转类型化错误
            last_error = exc

    raise ToolError(
        "tavily_unavailable",
        f"景点搜索失败（已重试 {MAX_ATTEMPTS - 1} 次）：{last_error}",
    )
