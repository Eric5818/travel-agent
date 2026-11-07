from __future__ import annotations

import json
import os
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.agent.json_utils import parse_json_array
from app.agent.prompts import (
    LODGING_EXTRACT_SYSTEM_PROMPT,
    LODGING_REPAIR_PROMPT,
)
from app.agent.tools.tavily_utils import (
    contains_number,
    is_cny_evidence,
    search_with_retry,
    text_of,
    urls_of,
)
from app.errors import ToolError
from app.schemas import CostRange, HotelOption

MAX_RESULTS = 5
MAX_HOTELS = 3


class LodgingResult(BaseModel):
    status: Literal["known", "unknown", "not_needed"]
    hotels: list[HotelOption] = Field(default_factory=list)
    nightly_range: CostRange | None = None
    note: str = ""


async def _extract(llm, payload: dict) -> list[dict]:
    base = [
        {"role": "system", "content": LODGING_EXTRACT_SYSTEM_PROMPT},
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
                    "content": LODGING_REPAIR_PROMPT.format(error=last_error),
                },
            ]
        last_text = await llm.complete(messages)
        items = parse_json_array(last_text)
        if items is None:
            last_error = "返回内容不是合法的 JSON 数组"
            continue
        return items
    return []


def _validate_hotel(item: dict, payload: dict) -> HotelOption | None:
    text = text_of(payload)
    urls = urls_of(payload)
    name = str(item.get("name", "")).strip()
    note = str(item.get("note", "")).strip()
    source_url = str(item.get("source_url", "")).strip()

    if not name or name not in text:
        return None
    try:
        minimum = float(item["min"])
        maximum = float(item["max"])
    except (KeyError, TypeError, ValueError):
        return None
    if minimum < 0 or maximum < minimum:
        return None
    if not (contains_number(text, minimum) and contains_number(text, maximum)):
        return None
    if not is_cny_evidence(text):
        return None
    if source_url not in urls:
        return None

    return HotelOption(
        name=name,
        price_per_night=CostRange(min=minimum, max=maximum),
        note=note,
        source_url=source_url,
    )


async def get_accommodation_options(
    city: str,
    accommodation: str,
    budget_level: str,
    start_date: str | None,
    nights: int,
    travelers: int,
    llm,
    client=None,
    api_key: str | None = None,
) -> LodgingResult:
    if accommodation == "不需要":
        return LodgingResult(status="not_needed", note="不需要住宿")

    month = (start_date or date.today().isoformat())[:7]
    query = (
        f"{city} {accommodation} {budget_level} 住宿 价格 "
        f"{month} {nights}晚 {travelers}人"
    )

    if client is None:
        key = (api_key or os.environ.get("TAVILY_API_KEY", "")).strip()
        if not key:
            return LodgingResult(
                status="unknown",
                note="未配置 TAVILY_API_KEY，无法查询住宿参考价",
            )
        from tavily import TavilyClient

        client = TavilyClient(api_key=key)

    try:
        payload = await search_with_retry(client, query, MAX_RESULTS)
    except ToolError:
        return LodgingResult(
            status="unknown", note="酒店查询失败，未查到参考价"
        )

    items = await _extract(llm, payload)
    hotels: list[HotelOption] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        hotel = _validate_hotel(item, payload)
        if hotel is not None:
            hotels.append(hotel)
        if len(hotels) >= MAX_HOTELS:
            break

    if not hotels:
        return LodgingResult(status="unknown", note="未查到可靠酒店参考价")

    nightly_range = CostRange(
        min=min(hotel.price_per_night.min for hotel in hotels),
        max=max(hotel.price_per_night.max for hotel in hotels),
    )
    note = (
        f"参考价，查询于 {date.today().isoformat()}；"
        "非实时库存，价格随日期浮动，以实际预订为准"
    )
    return LodgingResult(
        status="known", hotels=hotels, nightly_range=nightly_range, note=note
    )
