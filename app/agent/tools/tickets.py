from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from datetime import date

from pydantic import BaseModel

from app.agent.json_utils import parse_json_array
from app.agent.prompts import TICKET_EXTRACT_SYSTEM_PROMPT, TICKET_REPAIR_PROMPT
from app.agent.tools.tavily_utils import (
    contains_number,
    is_cny_evidence,
    search_with_retry,
)
from app.errors import ToolError
from app.schemas import Attraction, CostRange, TicketStatus

MAX_RESULTS = 3
CONCURRENCY = 5


class TicketInfo(BaseModel):
    attraction: str
    status: TicketStatus
    price: CostRange | None = None
    note: str = ""
    source_url: str | None = None


@dataclass
class _Bundle:
    attraction: str
    answer: str = ""
    results: list[dict] = field(default_factory=list)


def _unknown(name: str, note: str = "未查到可靠票价，需官网确认") -> TicketInfo:
    return TicketInfo(attraction=name, status="unknown", note=note)


def _bundle_text(bundle: _Bundle) -> str:
    parts = [bundle.answer]
    for item in bundle.results:
        parts.append(item.get("title", ""))
        parts.append(item.get("content", ""))
    return "\n".join(part for part in parts if part)


def _bundle_urls(bundle: _Bundle) -> set[str]:
    return {item.get("url", "") for item in bundle.results if item.get("url")}


def _with_date(note: str, today: date) -> str:
    base = note or "票价来自公开来源"
    return f"{base}（查询于 {today.isoformat()}，以景区官方为准）"


async def _fetch_bundle(
    city: str, attraction: Attraction, client, semaphore: asyncio.Semaphore
) -> _Bundle:
    query = f"{city} {attraction.name} 门票价格 官方 预约"
    async with semaphore:
        try:
            payload = await search_with_retry(client, query, MAX_RESULTS)
            return _Bundle(
                attraction=attraction.name,
                answer=payload.get("answer", ""),
                results=payload.get("results") or [],
            )
        except ToolError:
            return _Bundle(attraction=attraction.name, answer="", results=[])


async def _extract(llm, bundles: list[_Bundle]) -> list[dict]:
    payload = [
        {
            "index": index,
            "attraction": bundle.attraction,
            "answer": bundle.answer,
            "results": [
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "content": item.get("content", ""),
                }
                for item in bundle.results
            ],
        }
        for index, bundle in enumerate(bundles)
    ]
    base = [
        {"role": "system", "content": TICKET_EXTRACT_SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    last_text = ""
    last_error = ""
    for attempt in range(2):
        messages = base
        if attempt == 1:
            messages = base + [
                {"role": "assistant", "content": last_text},
                {
                    "role": "user",
                    "content": TICKET_REPAIR_PROMPT.format(error=last_error),
                },
            ]
        last_text = await llm.complete(messages)
        items = parse_json_array(last_text)
        if items is None:
            last_error = "返回内容不是合法的 JSON 数组"
            continue
        return items
    return []


def _validate_item(
    item: dict | None, bundle: _Bundle, today: date
) -> TicketInfo:
    if not item:
        return _unknown(bundle.attraction)

    text = _bundle_text(bundle)
    urls = _bundle_urls(bundle)
    status = str(item.get("status", "")).lower()
    note = str(item.get("note", "")).strip()
    source_url = str(item.get("source_url", "")).strip()

    if status == "free":
        if "免费" not in text:
            return _unknown(bundle.attraction, "免费证据不足，需官网确认")
        return TicketInfo(
            attraction=bundle.attraction,
            status="free",
            price=CostRange(min=0, max=0),
            note=_with_date(note or "来源标注免费", today),
            source_url=source_url if source_url in urls else None,
        )

    if status != "known":
        return _unknown(bundle.attraction)

    try:
        minimum = float(item["min"])
        maximum = float(item["max"])
    except (KeyError, TypeError, ValueError):
        return _unknown(bundle.attraction)

    if minimum < 0 or maximum < minimum:
        return _unknown(bundle.attraction)
    if not (contains_number(text, minimum) and contains_number(text, maximum)):
        return _unknown(bundle.attraction, "票价证据不足，需官网确认")
    if not is_cny_evidence(text):
        return _unknown(bundle.attraction, "无法确认人民币票价，需官网确认")
    if source_url not in urls:
        return _unknown(bundle.attraction, "票价来源不可追溯")

    return TicketInfo(
        attraction=bundle.attraction,
        status="known",
        price=CostRange(min=minimum, max=maximum),
        note=_with_date(note, today),
        source_url=source_url,
    )


async def get_ticket_prices(
    city: str,
    attractions: list[Attraction],
    llm,
    client=None,
    api_key: str | None = None,
    concurrency: int = CONCURRENCY,
) -> list[TicketInfo]:
    if not attractions:
        return []

    if client is None:
        key = (api_key or os.environ.get("TAVILY_API_KEY", "")).strip()
        if not key:
            return [
                _unknown(item.name, "未配置 TAVILY_API_KEY，无法查询票价")
                for item in attractions
            ]
        from tavily import TavilyClient

        client = TavilyClient(api_key=key)

    semaphore = asyncio.Semaphore(concurrency)
    bundles = await asyncio.gather(
        *[
            _fetch_bundle(city, attraction, client, semaphore)
            for attraction in attractions
        ]
    )

    extracted = await _extract(llm, bundles)
    by_index: dict[int, dict] = {}
    for item in extracted:
        if not isinstance(item, dict):
            continue
        try:
            by_index[int(item["index"])] = item
        except (KeyError, TypeError, ValueError):
            continue

    today = date.today()
    return [
        _validate_item(by_index.get(index), bundle, today)
        for index, bundle in enumerate(bundles)
    ]
