# 真实票价与住宿参考价 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为行程中的景点补充可追溯的真实票价，为住宿补充 2–3 家真实参考酒店，并用两者重算预算；查不到时明确标未知，不退回固定数字。

**Architecture:** 新增 `tickets.py` 与 `lodging.py` 两个独立工具，共用 Tavily 查询/证据校验助手；`ChatAgent` 在生成行程后回填票价、计算住宿区间并重算预算。

**Tech Stack:** Python 3.10、FastAPI、Pydantic v2、Tavily SDK、DeepSeek（OpenAI 兼容）、pytest、原生前端。

---

## 文件结构

```text
app/
├── agent/
│   ├── json_utils.py              # 新增：JSON 对象/数组解析
│   ├── prompts.py                 # 修改：票价/住宿抽取与修复提示词
│   ├── chat_agent.py              # 修改：票价、住宿、预算回填
│   └── tools/
│       ├── tavily_utils.py        # 新增：Tavily 重试与证据助手
│       ├── tickets.py             # 新增：真实票价工具
│       ├── lodging.py             # 新增：真实住宿参考工具
│       └── budget.py              # 修改：ticket_range / lodging_range
├── schemas.py                     # 修改：票价与住宿字段
├── static/app.js                  # 修改：票价、住宿参考、预算提示
└── static/style.css               # 修改：酒店卡片与票价样式
tests/
├── test_json_utils.py             # 新增
├── test_tavily_utils.py           # 新增
├── test_tickets.py                # 新增
├── test_lodging.py                # 新增
├── test_schemas.py                # 修改
├── test_budget.py                 # 修改
├── test_chat_agent.py             # 修改
└── test_e2e.py                    # 修改
```

---

## Task 1：JSON 解析工具与数据模型扩展

**Files:**
- Create: `app/agent/json_utils.py`
- Modify: `app/schemas.py`
- Test: `tests/test_json_utils.py`, `tests/test_schemas.py`

- [ ] **Step 1: 写失败测试 `tests/test_json_utils.py`**

```python
from app.agent.json_utils import parse_json_array, parse_json_object


def test_parse_json_object_accepts_plain_json():
    assert parse_json_object('{"a": 1}') == {"a": 1}


def test_parse_json_object_strips_code_fence():
    text = '```json\n{"a": 1}\n```'
    assert parse_json_object(text) == {"a": 1}


def test_parse_json_object_returns_none_for_invalid():
    assert parse_json_object("not json") is None
    assert parse_json_object("") is None


def test_parse_json_array_accepts_plain_json():
    assert parse_json_array('[{"a": 1}]') == [{"a": 1}]


def test_parse_json_array_strips_code_fence():
    text = '```json\n[{"a": 1}]\n```'
    assert parse_json_array(text) == [{"a": 1}]


def test_parse_json_array_returns_none_for_invalid():
    assert parse_json_array("not json") is None
    assert parse_json_array('{"a": 1}') is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `.\.venv\Scripts\python -m pytest tests/test_json_utils.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.agent.json_utils'`

- [ ] **Step 3: 实现 `app/agent/json_utils.py`**

```python
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
```

- [ ] **Step 4: 运行测试确认通过**

Run: `.\.venv\Scripts\python -m pytest tests/test_json_utils.py -v`
Expected: 6 passed

- [ ] **Step 5: 写失败测试 `tests/test_schemas.py` 的新增用例**

在文件末尾追加：

```python
def test_activity_ticket_fields_default_to_none():
    activity = Activity(
        time="09:00",
        name="故宫",
        type="attraction",
        duration_min=60,
        description="参观",
    )

    assert activity.ticket_status is None
    assert activity.ticket_note is None
    assert activity.ticket_source_url is None


def test_itinerary_accommodation_and_ticket_defaults():
    itinerary = make_itinerary()

    assert itinerary.accommodation_options == []
    assert itinerary.accommodation_status == "unknown"
    assert itinerary.accommodation_note is None
    assert itinerary.ticket_unknown_count == 0


def test_itinerary_with_ticket_and_hotel_round_trips():
    from app.schemas import HotelOption

    itinerary = make_itinerary()
    itinerary.ticket_unknown_count = 2
    itinerary.accommodation_status = "known"
    itinerary.accommodation_note = "参考价"
    itinerary.accommodation_options = [
        HotelOption(
            name="测试酒店",
            price_per_night=CostRange(min=400, max=600),
            note="含早",
            source_url="https://example.com/hotel",
        )
    ]
    itinerary.day_plans[0].activities[0].ticket_status = "known"
    itinerary.day_plans[0].activities[0].ticket_note = "查询于 2026-11-07"

    restored = Itinerary.model_validate(itinerary.model_dump(mode="json"))

    assert restored == itinerary
```

- [ ] **Step 6: 运行测试确认失败**

Run: `.\.venv\Scripts\python -m pytest tests/test_schemas.py -v`
Expected: FAIL，`AttributeError` 或 `ValidationError`（字段不存在）

- [ ] **Step 7: 修改 `app/schemas.py`**

在 `CostRange` 定义之后加入（`HotelOption` 依赖 `CostRange`，不能放在它前面）：

```python
TicketStatus = Literal["known", "free", "unknown"]
AccommodationStatus = Literal["known", "unknown", "not_needed"]


class HotelOption(BaseModel):
    name: str
    price_per_night: CostRange | None = None
    note: str = ""
    source_url: str | None = None
```

在 `Activity` 中追加字段：

```python
    ticket_status: TicketStatus | None = None
    ticket_note: str | None = None
    ticket_source_url: str | None = None
```

在 `Itinerary` 中追加字段：

```python
    accommodation_options: list[HotelOption] = Field(default_factory=list)
    accommodation_status: AccommodationStatus = "unknown"
    accommodation_note: str | None = None
    ticket_unknown_count: int = 0
```

- [ ] **Step 8: 运行全部测试**

Run: `.\.venv\Scripts\python -m pytest -q`
Expected: 现有测试 + 新增测试全部 PASS

- [ ] **Step 9: 提交**

```bash
git add app/agent/json_utils.py app/schemas.py tests/test_json_utils.py tests/test_schemas.py
git commit -m "feat: JSON 工具与票价/住宿数据模型"
```

---

## Task 2：预算接口支持真实区间

**Files:**
- Modify: `app/agent/tools/budget.py`
- Test: `tests/test_budget.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_budget.py` 末尾追加：

```python
def test_lodging_range_overrides_rate_table():
    result = estimate_budget(
        3, 2, "舒适", lodging_range=CostRange(min=1000, max=2000)
    )

    assert result.lodging == CostRange(min=1000, max=2000)


def test_ticket_range_is_used():
    result = estimate_budget(
        3, 2, "舒适", ticket_range=CostRange(min=100, max=200)
    )

    assert result.tickets == CostRange(min=100, max=200)


def test_real_ranges_are_included_in_total():
    result = estimate_budget(
        3,
        1,
        "舒适",
        ticket_range=CostRange(min=100, max=200),
        lodging_range=CostRange(min=800, max=1200),
    )

    assert result.total.min == pytest.approx(
        800 + result.food.min + result.local_transport.min + 100
    )
    assert result.total.max == pytest.approx(
        1200 + result.food.max + result.local_transport.max + 200
    )
```

需要在文件顶部确认已导入 `CostRange`；若没有，改为：

```python
from app.schemas import BudgetBreakdown, CostRange
```

- [ ] **Step 2: 运行测试确认失败**

Run: `.\.venv\Scripts\python -m pytest tests/test_budget.py -v`
Expected: FAIL，`TypeError: estimate_budget() got an unexpected keyword argument 'lodging_range'`

- [ ] **Step 3: 修改 `estimate_budget()` 签名与计算**

```python
def estimate_budget(
    days: int,
    travelers: int,
    budget_level: str,
    ticket_total: float = 0,
    city_tier: int = 1,
    ticket_range: CostRange | None = None,
    lodging_range: CostRange | None = None,
) -> BudgetBreakdown:
    if days <= 0:
        raise ValueError("days 必须大于 0")
    if travelers <= 0:
        raise ValueError("travelers 必须大于 0")
    if budget_level not in LODGING_RATE:
        raise ValueError(f"未知的预算档次：{budget_level!r}")
    if city_tier not in CITY_TIER_FACTOR:
        raise ValueError(f"未知的城市等级：{city_tier!r}")

    factor = CITY_TIER_FACTOR[city_tier]
    nights = days - 1 if days > 1 else 1

    if lodging_range is not None:
        lodging = lodging_range
    else:
        lodging = _range(LODGING_RATE[budget_level], nights * factor)

    food = _range(FOOD_RATE[budget_level], days * travelers * factor)
    local_transport = _range(
        LOCAL_TRANSPORT_RATE[budget_level], days * travelers * factor
    )
    if ticket_range is not None:
        tickets = ticket_range
    else:
        tickets = CostRange(
            min=round(ticket_total, 2), max=round(ticket_total, 2)
        )

    total = CostRange(
        min=round(
            lodging.min + food.min + local_transport.min + tickets.min, 2
        ),
        max=round(
            lodging.max + food.max + local_transport.max + tickets.max, 2
        ),
    )

    return BudgetBreakdown(
        lodging=lodging,
        food=food,
        local_transport=local_transport,
        tickets=tickets,
        total=total,
    )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `.\.venv\Scripts\python -m pytest tests/test_budget.py -v`
Expected: 11 passed

- [ ] **Step 5: 提交**

```bash
git add app/agent/tools/budget.py tests/test_budget.py
git commit -m "feat: 预算支持住宿与门票真实区间"
```

---

## Task 3：Tavily 查询与证据校验助手

**Files:**
- Create: `app/agent/tools/tavily_utils.py`
- Test: `tests/test_tavily_utils.py`

- [ ] **Step 1: 写失败测试**

```python
import asyncio

import pytest

from app.agent.tools.tavily_utils import (
    contains_number,
    is_cny_evidence,
    search_with_retry,
    text_of,
    urls_of,
)
from app.errors import ToolError


class FakeClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def search(self, query, **kwargs):
        self.calls += 1
        item = self._responses.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


@pytest.mark.asyncio
async def test_search_retries_once_then_succeeds():
    client = FakeClient([asyncio.TimeoutError("slow"), {"results": []}])

    payload = await search_with_retry(client, "北京 故宫", max_results=3)

    assert payload == {"results": []}
    assert client.calls == 2


@pytest.mark.asyncio
async def test_search_raises_after_two_failures():
    client = FakeClient(
        [asyncio.TimeoutError("slow"), asyncio.TimeoutError("slow")]
    )

    with pytest.raises(ToolError) as exc_info:
        await search_with_retry(client, "北京 故宫", max_results=3)

    assert exc_info.value.kind == "tavily_unavailable"


def test_text_and_urls_helpers():
    payload = {
        "answer": "故宫门票 60 元",
        "results": [
            {"title": "故宫", "content": "旺季 60 元", "url": "https://a"},
            {"title": "天坛", "content": "免费", "url": "https://b"},
        ],
    }

    assert "故宫门票 60 元" in text_of(payload)
    assert "旺季 60 元" in text_of(payload)
    assert urls_of(payload) == {"https://a", "https://b"}


def test_contains_number_uses_boundaries():
    assert contains_number("门票 60 元", 60) is True
    assert contains_number("门票 600 元", 60) is False
    assert contains_number("价格 60.5 元", 60.5) is True


def test_is_cny_evidence():
    assert is_cny_evidence("门票 60 元") is True
    assert is_cny_evidence("ticket 60 yuan") is True
    assert is_cny_evidence("ticket 60 USD") is False
    assert is_cny_evidence("60") is False
```

- [ ] **Step 2: 运行测试确认失败**

Run: `.\.venv\Scripts\python -m pytest tests/test_tavily_utils.py -v`
Expected: FAIL，`ModuleNotFoundError`

- [ ] **Step 3: 实现 `app/agent/tools/tavily_utils.py`**

```python
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
) -> dict:
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(
                    client.search,
                    query,
                    search_depth="advanced",
                    include_answer=True,
                    max_results=max_results,
                ),
                timeout=timeout,
            )
        except Exception as exc:  # noqa: BLE001 - 工具边界统一转类型化错误
            last_error = exc
    raise ToolError(
        "tavily_unavailable", f"Tavily 查询失败（已重试 {attempts - 1} 次）：{last_error}"
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
```

- [ ] **Step 4: 运行测试确认通过**

Run: `.\.venv\Scripts\python -m pytest tests/test_tavily_utils.py -v`
Expected: 5 passed

- [ ] **Step 5: 提交**

```bash
git add app/agent/tools/tavily_utils.py tests/test_tavily_utils.py
git commit -m "feat: Tavily 重试与价格证据校验助手"
```

---

## Task 4：真实票价工具

**Files:**
- Create: `app/agent/tools/tickets.py`
- Modify: `app/agent/prompts.py`
- Test: `tests/test_tickets.py`

- [ ] **Step 1: 在 `app/agent/prompts.py` 末尾追加提示词**

```python
TICKET_EXTRACT_SYSTEM_PROMPT = """你是景点票价抽取器。输入是 JSON 数组，每项包含 index、attraction、answer、results。

只输出一个 JSON 数组，不要输出 markdown 代码块、解释或多余文字。每项格式：
{"index": 0, "status": "known", "min": 60, "max": 60, "note": "旺季60元，淡季40元", "source_url": "https://..."}

规则：
1. status 只能是 known、free、unknown。
2. 只取标准成人票；同一景点有旺季/淡季或多档价格时，取最低–最高区间。
3. 排除学生票、老年票、儿童票、团队票、联票、讲解费、导览费。
4. 只有来源明确写「免费」才输出 free，min/max 填 0。
5. 没有可靠数字时输出 unknown，min/max 填 0。
6. source_url 必须是输入 results 中出现的 URL。
7. 禁止猜测、编造价格或来源。
"""

TICKET_REPAIR_PROMPT = """上面的输出不是合法的 JSON 数组，错误如下：
{error}

请只修复结构与字段类型，保持已有事实不变，重新只输出一个 JSON 数组。
"""
```

- [ ] **Step 2: 写失败测试 `tests/test_tickets.py`**

```python
import asyncio
import json

import pytest

from app.agent.tools.tickets import TicketInfo, get_ticket_prices
from app.schemas import Attraction


class FakeTavily:
    def __init__(self, responses):
        self.responses = responses
        self.queries = []

    def search(self, query, **kwargs):
        self.queries.append(query)
        for key, value in self.responses.items():
            if key in query:
                if isinstance(value, BaseException):
                    raise value
                return value
        raise AssertionError(f"unexpected query: {query}")


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    async def complete(self, messages):
        self.calls += 1
        return self.responses.pop(0)


def attraction(name: str) -> Attraction:
    return Attraction(name=name, category="历史", source_url="https://example.com")


def payload(answer: str, url: str, content: str) -> dict:
    return {
        "answer": answer,
        "results": [{"title": "来源", "url": url, "content": content}],
    }


@pytest.mark.asyncio
async def test_known_free_and_unknown_statuses():
    requests = {
        "故宫": payload("故宫门票 60 元", "https://a", "旺季 60 元"),
        "天坛": payload("天坛免费开放", "https://b", "免费"),
        "颐和园": payload("颐和园门票 30 元", "https://c", "门票 30 元"),
    }
    llm = FakeLLM(
        [
            json.dumps(
                [
                    {"index": 0, "status": "known", "min": 60, "max": 60, "note": "成人票", "source_url": "https://a"},
                    {"index": 1, "status": "free", "min": 0, "max": 0, "note": "", "source_url": "https://b"},
                    {"index": 2, "status": "unknown", "min": 0, "max": 0, "note": "", "source_url": ""},
                ],
                ensure_ascii=False,
            )
        ]
    )
    client = FakeTavily(requests)

    result = await get_ticket_prices(
        "北京", [attraction("故宫"), attraction("天坛"), attraction("颐和园")], llm, client=client
    )

    assert [item.status for item in result] == ["known", "free", "unknown"]
    assert result[0].price.min == 60
    assert "查询于" in result[0].note
    assert result[1].price.min == 0
    assert result[2].price is None


@pytest.mark.asyncio
async def test_fabricated_price_is_rejected():
    llm = FakeLLM(
        [
            json.dumps(
                [{"index": 0, "status": "known", "min": 999, "max": 999, "note": "", "source_url": "https://a"}],
                ensure_ascii=False,
            )
        ]
    )
    client = FakeTavily({"故宫": payload("故宫门票 60 元", "https://a", "60 元")})

    result = await get_ticket_prices("北京", [attraction("故宫")], llm, client=client)

    assert result[0].status == "unknown"
    assert result[0].price is None


@pytest.mark.asyncio
async def test_source_url_must_belong_to_results():
    llm = FakeLLM(
        [
            json.dumps(
                [{"index": 0, "status": "known", "min": 60, "max": 60, "note": "", "source_url": "https://evil"}],
                ensure_ascii=False,
            )
        ]
    )
    client = FakeTavily({"故宫": payload("故宫门票 60 元", "https://a", "60 元")})

    result = await get_ticket_prices("北京", [attraction("故宫")], llm, client=client)

    assert result[0].status == "unknown"


@pytest.mark.asyncio
async def test_invalid_json_is_repaired_once():
    llm = FakeLLM(
        [
            "not json",
            json.dumps(
                [{"index": 0, "status": "known", "min": 60, "max": 60, "note": "", "source_url": "https://a"}],
                ensure_ascii=False,
            ),
        ]
    )
    client = FakeTavily({"故宫": payload("故宫门票 60 元", "https://a", "60 元")})

    result = await get_ticket_prices("北京", [attraction("故宫")], llm, client=client)

    assert result[0].status == "known"
    assert llm.calls == 2


@pytest.mark.asyncio
async def test_invalid_json_twice_marks_unknown():
    llm = FakeLLM(["not json", "still not json"])
    client = FakeTavily({"故宫": payload("故宫门票 60 元", "https://a", "60 元")})

    result = await get_ticket_prices("北京", [attraction("故宫")], llm, client=client)

    assert result[0].status == "unknown"


@pytest.mark.asyncio
async def test_single_search_failure_does_not_block_others():
    llm = FakeLLM(
        [
            json.dumps(
                [{"index": 1, "status": "known", "min": 30, "max": 30, "note": "", "source_url": "https://c"}],
                ensure_ascii=False,
            )
        ]
    )
    client = FakeTavily(
        {
            "故宫": asyncio.TimeoutError("slow"),
            "颐和园": payload("颐和园门票 30 元", "https://c", "30 元"),
        }
    )

    result = await get_ticket_prices(
        "北京", [attraction("故宫"), attraction("颐和园")], llm, client=client
    )

    assert result[0].status == "unknown"
    assert result[1].status == "known"


@pytest.mark.asyncio
async def test_empty_attractions_do_not_call_anything():
    llm = FakeLLM([])
    client = FakeTavily({})

    result = await get_ticket_prices("北京", [], llm, client=client)

    assert result == []
    assert llm.calls == 0
    assert client.queries == []
```

- [ ] **Step 3: 运行测试确认失败**

Run: `.\.venv\Scripts\python -m pytest tests/test_tickets.py -v`
Expected: FAIL，`ModuleNotFoundError`

- [ ] **Step 4: 实现 `app/agent/tools/tickets.py`**

```python
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
```

```python
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
                {"role": "user", "content": TICKET_REPAIR_PROMPT.format(error=last_error)},
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
```

- [ ] **Step 5: 运行测试确认通过**

Run: `.\.venv\Scripts\python -m pytest tests/test_tickets.py -v`
Expected: 7 passed

- [ ] **Step 6: 提交**

```bash
git add app/agent/tools/tickets.py app/agent/prompts.py tests/test_tickets.py
git commit -m "feat: 真实景点票价查询与证据校验"
```

---

## Task 5：真实住宿参考工具

**Files:**
- Create: `app/agent/tools/lodging.py`
- Modify: `app/agent/prompts.py`
- Test: `tests/test_lodging.py`

- [ ] **Step 1: 在 `app/agent/prompts.py` 末尾追加**

```python
LODGING_EXTRACT_SYSTEM_PROMPT = """你是酒店参考价抽取器。输入是 JSON，包含 city、month、nights、travelers、answer、results。

只输出一个 JSON 数组，最多 3 家酒店，不要输出 markdown 代码块或解释。每项格式：
{"name": "酒店名", "min": 450, "max": 650, "note": "含早", "source_url": "https://..."}

规则：
1. 只接受标准房型的每晚人民币价格；只给总价、套餐价或无法判断时不要输出。
2. 排除税费、服务费、押金、餐饮套餐、钟点房。
3. 酒店名必须真实出现在输入 results 的标题或摘要中。
4. source_url 必须是输入 results 中出现的 URL。
5. 最多 3 家；没有可靠酒店时输出 []。
6. 禁止猜测或编造。
"""

LODGING_REPAIR_PROMPT = """上面的输出不是合法的 JSON 数组，错误如下：
{error}

请只修复结构与字段类型，保持已有事实不变，重新只输出一个 JSON 数组。
"""
```

- [ ] **Step 2: 写失败测试 `tests/test_lodging.py`**

```python
import json
from datetime import date

import pytest

from app.agent.tools.lodging import LodgingResult, get_accommodation_options


class FakeTavily:
    def __init__(self, payload=None, exc=None):
        self.payload = payload
        self.exc = exc
        self.queries = []

    def search(self, query, **kwargs):
        self.queries.append(query)
        if self.exc is not None:
            raise self.exc
        return self.payload


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    async def complete(self, messages):
        self.calls += 1
        return self.responses.pop(0)


def hotel_payload() -> dict:
    return {
        "answer": "参考酒店：北京饭店 500 元/晚，王府井民宿 450–600 元/晚",
        "results": [
            {
                "title": "北京饭店",
                "url": "https://a",
                "content": "北京饭店标准间 500 元/晚，含早",
            },
            {
                "title": "王府井民宿",
                "url": "https://b",
                "content": "王府井民宿 450–600 元/晚",
            },
        ],
    }


@pytest.mark.asyncio
async def test_known_hotels_and_nightly_range():
    llm = FakeLLM(
        [
            json.dumps(
                [
                    {"name": "北京饭店", "min": 500, "max": 500, "note": "含早", "source_url": "https://a"},
                    {"name": "王府井民宿", "min": 450, "max": 600, "note": "起价", "source_url": "https://b"},
                ],
                ensure_ascii=False,
            )
        ]
    )
    client = FakeTavily(hotel_payload())

    result = await get_accommodation_options(
        "北京", "酒店", "舒适", "2026-11-20", 2, 2, llm, client=client
    )

    assert result.status == "known"
    assert len(result.hotels) == 2
    assert result.nightly_range.min == 450
    assert result.nightly_range.max == 600
    assert "非实时库存" in result.note


@pytest.mark.asyncio
async def test_not_needed_skips_query():
    llm = FakeLLM([])
    client = FakeTavily(hotel_payload())

    result = await get_accommodation_options(
        "北京", "不需要", "舒适", None, 2, 2, llm, client=client
    )

    assert result.status == "not_needed"
    assert client.queries == []
    assert llm.calls == 0


@pytest.mark.asyncio
async def test_search_failure_returns_unknown():
    llm = FakeLLM([])
    client = FakeTavily(exc=RuntimeError("boom"))

    result = await get_accommodation_options(
        "北京", "酒店", "舒适", None, 2, 2, llm, client=client
    )

    assert result.status == "unknown"
    assert result.hotels == []


@pytest.mark.asyncio
async def test_hotel_with_unknown_name_is_discarded():
    llm = FakeLLM(
        [
            json.dumps(
                [{"name": "不存在的酒店", "min": 500, "max": 500, "note": "", "source_url": "https://a"}],
                ensure_ascii=False,
            )
        ]
    )
    client = FakeTavily(hotel_payload())

    result = await get_accommodation_options(
        "北京", "酒店", "舒适", None, 2, 2, llm, client=client
    )

    assert result.status == "unknown"


@pytest.mark.asyncio
async def test_more_than_three_hotels_are_truncated():
    items = [
        {"name": "A酒店", "min": 100, "max": 100, "note": "", "source_url": "https://a"},
        {"name": "B酒店", "min": 200, "max": 200, "note": "", "source_url": "https://b"},
        {"name": "C酒店", "min": 300, "max": 300, "note": "", "source_url": "https://c"},
        {"name": "D酒店", "min": 400, "max": 400, "note": "", "source_url": "https://d"},
    ]
    payload = {
        "answer": "A酒店 100 元，B酒店 200 元，C酒店 300 元，D酒店 400 元",
        "results": [
            {"title": "A酒店", "url": "https://a", "content": "A酒店 100 元/晚"},
            {"title": "B酒店", "url": "https://b", "content": "B酒店 200 元/晚"},
            {"title": "C酒店", "url": "https://c", "content": "C酒店 300 元/晚"},
            {"title": "D酒店", "url": "https://d", "content": "D酒店 400 元/晚"},
        ],
    }
    llm = FakeLLM([json.dumps(items, ensure_ascii=False)])

    result = await get_accommodation_options(
        "北京", "酒店", "舒适", None, 2, 2, llm, client=FakeTavily(payload)
    )

    assert len(result.hotels) == 3


@pytest.mark.asyncio
async def test_invalid_json_is_repaired_once():
    llm = FakeLLM(
        [
            "bad",
            json.dumps(
                [{"name": "北京饭店", "min": 500, "max": 500, "note": "", "source_url": "https://a"}],
                ensure_ascii=False,
            ),
        ]
    )
    client = FakeTavily(hotel_payload())

    result = await get_accommodation_options(
        "北京", "酒店", "舒适", None, 2, 2, llm, client=client
    )

    assert result.status == "known"
    assert llm.calls == 2


@pytest.mark.asyncio
async def test_invalid_json_twice_returns_unknown():
    llm = FakeLLM(["bad", "still bad"])
    client = FakeTavily(hotel_payload())

    result = await get_accommodation_options(
        "北京", "酒店", "舒适", None, 2, 2, llm, client=client
    )

    assert result.status == "unknown"
```

- [ ] **Step 3: 运行测试确认失败**

Run: `.\.venv\Scripts\python -m pytest tests/test_lodging.py -v`
Expected: FAIL，`ModuleNotFoundError`

- [ ] **Step 4: 实现 `app/agent/tools/lodging.py`**

```python
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
                {"role": "user", "content": LODGING_REPAIR_PROMPT.format(error=last_error)},
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
                status="unknown", note="未配置 TAVILY_API_KEY，无法查询住宿参考价"
            )
        from tavily import TavilyClient

        client = TavilyClient(api_key=key)

    try:
        payload = await search_with_retry(client, query, MAX_RESULTS)
    except ToolError:
        return LodgingResult(status="unknown", note="酒店查询失败，未查到参考价")

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
```

- [ ] **Step 5: 运行测试确认通过**

Run: `.\.venv\Scripts\python -m pytest tests/test_lodging.py -v`
Expected: 7 passed

- [ ] **Step 6: 提交**

```bash
git add app/agent/tools/lodging.py app/agent/prompts.py tests/test_lodging.py
git commit -m "feat: 真实住宿参考价查询与证据校验"
```

---

## Task 6：ChatAgent 集成票价、住宿与预算回填

**Files:**
- Modify: `app/agent/chat_agent.py`
- Test: `tests/test_chat_agent.py`

- [ ] **Step 1: 修改测试的 FakeTools 与 make_agent**

在 `tests/test_chat_agent.py` 顶部补充导入：

```python
from app.agent.tools.lodging import LodgingResult
from app.agent.tools.tickets import TicketInfo
from app.schemas import Attraction, HotelOption
```

把 `FakeTools` 替换为：

```python
class FakeTools:
    def __init__(
        self,
        search_error=None,
        attractions=None,
        ticket_infos=None,
        lodging_result=None,
    ):
        self.calls = {
            "search": 0,
            "tickets": 0,
            "lodging": 0,
            "weather": 0,
            "budget": 0,
        }
        self.search_error = search_error
        self.attractions = attractions or []
        self.ticket_infos = ticket_infos or []
        self.lodging_result = lodging_result or LodgingResult(
            status="known",
            hotels=[
                HotelOption(
                    name="测试酒店",
                    price_per_night=CostRange(min=400, max=600),
                    source_url="https://hotel.example.com",
                )
            ],
            nightly_range=CostRange(min=400, max=600),
            note="参考价",
        )

    async def search(self, city, keywords, limit=8):
        self.calls["search"] += 1
        if self.search_error is not None:
            raise self.search_error
        return self.attractions

    async def tickets(self, city, attractions):
        self.calls["tickets"] += 1
        return self.ticket_infos

    async def lodging(self, city, accommodation, budget_level, start_date, nights, travelers):
        self.calls["lodging"] += 1
        return self.lodging_result

    async def weather(self, city, start_date, days):
        self.calls["weather"] += 1
        return [
            WeatherInfo(
                date=start_date,
                weather_desc="晴",
                temp_high_c=10,
                temp_low_c=2,
                chance_of_rain=0,
            )
        ]

    def budget(
        self,
        days,
        travelers,
        budget_level,
        ticket_total=0,
        city_tier=1,
        ticket_range=None,
        lodging_range=None,
    ):
        self.calls["budget"] += 1
        lodging = lodging_range or CostRange(min=0, max=0)
        tickets = ticket_range or CostRange(
            min=ticket_total, max=ticket_total
        )
        return BudgetBreakdown(
            lodging=lodging,
            food=CostRange(min=150, max=300),
            local_transport=CostRange(min=30, max=60),
            tickets=tickets,
            total=CostRange(
                min=lodging.min + 150 + 30 + tickets.min,
                max=lodging.max + 300 + 60 + tickets.max,
            ),
        )
```

把 `make_agent` 替换为：

```python
def make_agent(llm, tools=None, **kwargs):
    tools = tools or FakeTools()
    return ChatAgent(
        llm=llm,
        search_attractions=tools.search,
        get_ticket_prices=tools.tickets,
        get_accommodation_options=tools.lodging,
        get_weather=tools.weather,
        estimate_budget=tools.budget,
        **kwargs,
    ), tools
```

把 `test_confirmed_plan_calls_tools_and_returns_itinerary` 中的断言：

```python
    assert tools.calls == {"search": 1, "weather": 1, "budget": 1}
```

改为：

```python
    assert tools.calls == {
        "search": 1,
        "tickets": 0,
        "lodging": 1,
        "weather": 1,
        "budget": 1,
    }
```

- [ ] **Step 2: 追加新测试**

在文件末尾追加：

```python
def known_ticket() -> TicketInfo:
    return TicketInfo(
        attraction="故宫",
        status="known",
        price=CostRange(min=60, max=60),
        note="门票 60 元（查询于 2026-11-07）",
        source_url="https://ticket.example.com",
    )


def known_lodging() -> LodgingResult:
    return LodgingResult(
        status="known",
        hotels=[
            HotelOption(
                name="测试酒店",
                price_per_night=CostRange(min=400, max=600),
                source_url="https://hotel.example.com",
            )
        ],
        nightly_range=CostRange(min=400, max=600),
        note="参考价，查询于 2026-11-07",
    )


@pytest.mark.asyncio
async def test_ticket_prices_are_patched_and_budgeted():
    llm = FakeLLM(
        [
            extraction(
                destination="北京",
                days=3,
                preferences=["历史"],
                travelers=2,
                intent="plan",
            ),
            json.dumps(GOOD_ITINERARY, ensure_ascii=False),
        ]
    )
    tools = FakeTools(
        attractions=[Attraction(name="故宫", category="历史")],
        ticket_infos=[known_ticket()],
        lodging_result=known_lodging(),
    )
    agent, _ = make_agent(llm, tools=tools)
    session = FakeSession()

    turn = await agent.handle("开始规划", session)

    itinerary = turn.itinerary
    assert itinerary is not None
    activity = itinerary.day_plans[0].activities[0]
    assert activity.ticket_status == "known"
    assert activity.cost_estimate == CostRange(min=60, max=60)
    assert itinerary.ticket_unknown_count == 0
    # 2 人 1 间 × 2 晚：400–600 × 2
    assert itinerary.budget.lodging == CostRange(min=800, max=1200)
    # 门票：60 × 2 人
    assert itinerary.budget.tickets == CostRange(min=120, max=120)
    assert itinerary.accommodation_status == "known"


@pytest.mark.asyncio
async def test_unknown_ticket_is_not_budgeted():
    llm = FakeLLM(
        [
            extraction(
                destination="北京",
                days=3,
                preferences=["历史"],
                intent="plan",
            ),
            json.dumps(GOOD_ITINERARY, ensure_ascii=False),
        ]
    )
    tools = FakeTools(
        attractions=[Attraction(name="故宫", category="历史")],
        ticket_infos=[
            TicketInfo(
                attraction="故宫",
                status="unknown",
                note="未查到可靠票价",
            )
        ],
        lodging_result=known_lodging(),
    )
    agent, _ = make_agent(llm, tools=tools)
    session = FakeSession()

    turn = await agent.handle("开始规划", session)

    itinerary = turn.itinerary
    assert itinerary.day_plans[0].activities[0].ticket_status == "unknown"
    assert itinerary.day_plans[0].activities[0].cost_estimate is None
    assert itinerary.ticket_unknown_count == 1
    assert itinerary.budget.tickets == CostRange(min=0, max=0)


@pytest.mark.asyncio
async def test_unknown_lodging_does_not_fall_back_to_rate_table():
    llm = FakeLLM(
        [
            extraction(
                destination="北京",
                days=3,
                preferences=["历史"],
                intent="plan",
            ),
            json.dumps(GOOD_ITINERARY, ensure_ascii=False),
        ]
    )
    tools = FakeTools(
        attractions=[Attraction(name="故宫", category="历史")],
        ticket_infos=[known_ticket()],
        lodging_result=LodgingResult(
            status="unknown", note="未查到可靠酒店参考价"
        ),
    )
    agent, _ = make_agent(llm, tools=tools)
    session = FakeSession()

    turn = await agent.handle("开始规划", session)

    itinerary = turn.itinerary
    assert itinerary.accommodation_status == "unknown"
    assert itinerary.budget.lodging == CostRange(min=0, max=0)


@pytest.mark.asyncio
async def test_not_needed_accommodation_skips_lodging_query():
    llm = FakeLLM(
        [
            extraction(
                destination="北京",
                days=3,
                preferences=["历史"],
                accommodation="不需要",
                intent="plan",
            ),
            json.dumps(GOOD_ITINERARY, ensure_ascii=False),
        ]
    )
    tools = FakeTools(
        attractions=[Attraction(name="故宫", category="历史")],
        ticket_infos=[known_ticket()],
    )
    agent, _ = make_agent(llm, tools=tools)
    session = FakeSession()

    turn = await agent.handle("开始规划", session)

    itinerary = turn.itinerary
    assert tools.calls["lodging"] == 0
    assert itinerary.accommodation_status == "not_needed"
    assert itinerary.budget.lodging == CostRange(min=0, max=0)
```

- [ ] **Step 3: 运行测试确认失败**

Run: `.\.venv\Scripts\python -m pytest tests/test_chat_agent.py -v`
Expected: FAIL，`TypeError: ChatAgent.__init__() got an unexpected keyword argument 'get_ticket_prices'`

- [ ] **Step 4: 修改 `app/agent/chat_agent.py` 导入与构造函数**

顶部追加：

```python
import math

from app.agent.json_utils import parse_json_object
from app.agent.tools.lodging import (
    LodgingResult,
    get_accommodation_options as default_get_accommodation_options,
)
from app.agent.tools.tickets import (
    TicketInfo,
    get_ticket_prices as default_get_ticket_prices,
)
from app.schemas import BudgetBreakdown, CostRange, Itinerary
```

删除本地 `_parse_json_object` 函数，并把 `_extract` 中的调用改为 `parse_json_object`。

构造函数增加参数并赋值：

```python
    def __init__(
        self,
        llm: LLM,
        search_attractions=None,
        get_weather=None,
        estimate_budget=None,
        get_ticket_prices=None,
        get_accommodation_options=None,
        max_tool_calls: int = MAX_TOOL_CALLS,
    ):
        self.llm = llm
        self.search_attractions = search_attractions or default_search_attractions
        self.get_weather = get_weather or default_get_weather
        self.estimate_budget = estimate_budget or default_estimate_budget
        self.get_ticket_prices = (
            get_ticket_prices or self._default_ticket_prices
        )
        self.get_accommodation_options = (
            get_accommodation_options or self._default_accommodation_options
        )
        self.max_tool_calls = max_tool_calls
        self._tool_calls = 0

    async def _default_ticket_prices(self, city, attractions):
        return await default_get_ticket_prices(
            city, attractions, llm=self.llm
        )

    async def _default_accommodation_options(
        self, city, accommodation, budget_level, start_date, nights, travelers
    ):
        return await default_get_accommodation_options(
            city,
            accommodation,
            budget_level,
            start_date,
            nights,
            travelers,
            llm=self.llm,
        )
```

- [ ] **Step 5: 替换 `_plan` 并新增回填方法**

```python
    async def _plan(self, profile: TripProfile, session) -> AgentTurn:
        city = profile.destination
        start_date = (
            profile.start_date.isoformat()
            if profile.start_date is not None
            else date.today().isoformat()
        )
        nights = profile.days - 1 if profile.days > 1 else 1

        self._consume_tool_call()
        attractions = await self.search_attractions(city, profile.preferences)

        ticket_infos: list[TicketInfo] = []
        if attractions:
            self._consume_tool_call()
            ticket_infos = await self.get_ticket_prices(city, attractions)

        if profile.accommodation == "不需要":
            lodging = LodgingResult(status="not_needed", note="不需要住宿")
        else:
            self._consume_tool_call()
            lodging = await self.get_accommodation_options(
                city,
                profile.accommodation,
                profile.budget_level,
                start_date,
                nights,
                profile.travelers,
            )

        self._consume_tool_call()
        weather = await self.get_weather(city, start_date, profile.days)

        rooms = max(1, math.ceil(profile.travelers / 2))
        if lodging.status == "known" and lodging.nightly_range is not None:
            lodging_range = CostRange(
                min=round(lodging.nightly_range.min * nights * rooms, 2),
                max=round(lodging.nightly_range.max * nights * rooms, 2),
            )
        else:
            lodging_range = CostRange(min=0, max=0)

        placeholder_budget = BudgetBreakdown(
            lodging=CostRange(min=0, max=0),
            food=CostRange(min=0, max=0),
            local_transport=CostRange(min=0, max=0),
            tickets=CostRange(min=0, max=0),
            total=CostRange(min=0, max=0),
        )

        itinerary = await self._generate_itinerary(
            profile, attractions, weather, placeholder_budget
        )

        unknown_count = self._apply_ticket_prices(itinerary, ticket_infos)
        ticket_range = self._ticket_range(
            itinerary, ticket_infos, profile.travelers
        )

        self._consume_tool_call()
        budget = self.estimate_budget(
            profile.days,
            profile.travelers,
            profile.budget_level,
            ticket_range=ticket_range,
            lodging_range=lodging_range,
        )
        itinerary.budget = budget

        itinerary.ticket_unknown_count = unknown_count
        itinerary.accommodation_options = lodging.hotels
        itinerary.accommodation_status = lodging.status
        itinerary.accommodation_note = lodging.note or None

        reply = (
            f"已为你生成{city}{profile.days}天的行程，"
            "包含每日安排、天气、票价和住宿参考。"
        )
        return AgentTurn(reply=reply, profile=profile, itinerary=itinerary)

    def _apply_ticket_prices(
        self, itinerary: Itinerary, ticket_infos: list[TicketInfo]
    ) -> int:
        by_name = {info.attraction: info for info in ticket_infos}
        unknown: set[str] = set()

        for day in itinerary.day_plans:
            for activity in day.activities:
                if activity.type != "attraction":
                    continue
                info = by_name.get(activity.name.strip())
                if info is None:
                    activity.ticket_status = "unknown"
                    activity.cost_estimate = None
                    activity.ticket_note = "未查到该景点票价，需官网确认"
                    unknown.add(activity.name)
                    continue
                if info.status == "free":
                    activity.ticket_status = "free"
                    activity.cost_estimate = CostRange(min=0, max=0)
                    activity.ticket_note = info.note
                    activity.ticket_source_url = info.source_url
                elif info.status == "known" and info.price is not None:
                    activity.ticket_status = "known"
                    activity.cost_estimate = info.price
                    activity.ticket_note = info.note
                    activity.ticket_source_url = info.source_url
                else:
                    activity.ticket_status = "unknown"
                    activity.cost_estimate = None
                    activity.ticket_note = (
                        info.note or "票价未知，需官网确认"
                    )
                    activity.ticket_source_url = info.source_url
                    unknown.add(activity.name)

        return len(unknown)

    def _ticket_range(
        self,
        itinerary: Itinerary,
        ticket_infos: list[TicketInfo],
        travelers: int,
    ) -> CostRange:
        by_name = {
            info.attraction: info
            for info in ticket_infos
            if info.status in {"known", "free"} and info.price is not None
        }
        used: dict[str, CostRange] = {}
        for day in itinerary.day_plans:
            for activity in day.activities:
                if activity.type != "attraction":
                    continue
                info = by_name.get(activity.name.strip())
                if info is not None and info.price is not None:
                    used[activity.name] = info.price

        if not used:
            return CostRange(min=0, max=0)

        minimum = sum(price.min for price in used.values()) * travelers
        maximum = sum(price.max for price in used.values()) * travelers
        return CostRange(min=round(minimum, 2), max=round(maximum, 2))
```

- [ ] **Step 6: 运行测试**

Run: `.\.venv\Scripts\python -m pytest tests/test_chat_agent.py -v`
Expected: 11 passed

- [ ] **Step 7: 运行全量测试**

Run: `.\.venv\Scripts\python -m pytest -q`
Expected: 全部 PASS

- [ ] **Step 8: 提交**

```bash
git add app/agent/chat_agent.py tests/test_chat_agent.py
git commit -m "feat: ChatAgent 回填票价与住宿并重算预算"
```

---

## Task 7：前端票价与住宿参考展示

**Files:**
- Modify: `app/static/app.js`
- Modify: `app/static/style.css`

- [ ] **Step 1: 修改 `app/static/app.js` 的活动渲染**

在 `renderDay` 之前加入：

```javascript
function ticketText(activity) {
  if (activity.type !== 'attraction') {
    return '';
  }
  if (activity.ticket_status === 'free') {
    return '免费';
  }
  if (activity.ticket_status === 'known' && activity.cost_estimate) {
    return `门票 ${money(activity.cost_estimate.min)}–${money(activity.cost_estimate.max)}`;
  }
  if (activity.ticket_status === 'unknown') {
    return '票价未知，需官网确认';
  }
  if (activity.cost_estimate && Number(activity.cost_estimate.max) > 0) {
    return `门票 ${money(activity.cost_estimate.min)}–${money(activity.cost_estimate.max)}`;
  }
  return '';
}
```

把 `renderDay` 中构造 `metaParts` 的代码替换为：

```javascript
    const metaParts = [];
    if (activity.duration_min) {
      metaParts.push(`${activity.duration_min} 分钟`);
    }
    const ticketLabel = ticketText(activity);
    if (ticketLabel) {
      metaParts.push(ticketLabel);
    }
```

在 `body.append(name, meta, description);` 之后加入：

```javascript
    if (activity.ticket_note) {
      const ticketNote = document.createElement('p');
      ticketNote.className = 'ticket-note';
      ticketNote.textContent = activity.ticket_note;
      body.appendChild(ticketNote);
    }
    if (activity.ticket_source_url) {
      const ticketLink = document.createElement('a');
      ticketLink.href = activity.ticket_source_url;
      ticketLink.target = '_blank';
      ticketLink.rel = 'noopener noreferrer';
      ticketLink.textContent = '票价来源';
      body.appendChild(ticketLink);
    }
```

- [ ] **Step 2: 增加住宿参考渲染**

在 `renderBudget` 之前加入：

```javascript
function renderAccommodation(itinerary) {
  const status = itinerary.accommodation_status;
  if (!status) {
    return null;
  }

  const section = document.createElement('section');
  section.className = 'accommodation-section';

  const heading = document.createElement('h2');
  heading.textContent = '住宿参考';
  section.appendChild(heading);

  if (status === 'not_needed') {
    const note = document.createElement('p');
    note.className = 'accommodation-note';
    note.textContent = '本次行程不需要住宿。';
    section.appendChild(note);
    return section;
  }

  const hotels = itinerary.accommodation_options || [];
  if (status !== 'known' || hotels.length === 0) {
    const note = document.createElement('p');
    note.className = 'accommodation-note';
    note.textContent = '未查到真实住宿参考价，预算未计入住宿费用。';
    section.appendChild(note);
    return section;
  }

  const list = document.createElement('div');
  list.className = 'hotel-list';
  for (const hotel of hotels) {
    const card = document.createElement('article');
    card.className = 'hotel-card';

    const name = document.createElement('h4');
    name.textContent = hotel.name;

    const price = document.createElement('p');
    price.className = 'hotel-price';
    price.textContent = hotel.price_per_night
      ? `${money(hotel.price_per_night.min)} – ${money(hotel.price_per_night.max)} / 晚`
      : '价格未知';

    card.append(name, price);

    if (hotel.note) {
      const note = document.createElement('p');
      note.className = 'muted';
      note.textContent = hotel.note;
      card.appendChild(note);
    }
    if (hotel.source_url) {
      const link = document.createElement('a');
      link.href = hotel.source_url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.textContent = '查看来源';
      card.appendChild(link);
    }
    list.appendChild(card);
  }
  section.appendChild(list);

  if (itinerary.accommodation_note) {
    const note = document.createElement('p');
    note.className = 'accommodation-note';
    note.textContent = itinerary.accommodation_note;
    section.appendChild(note);
  }
  return section;
}
```

- [ ] **Step 3: 修改预算表**

把 `renderBudget(budget)` 改为 `renderBudget(itinerary)`：

```javascript
function renderBudget(itinerary) {
  const budget = itinerary.budget;
  const table = document.createElement('table');
  table.className = 'budget-table';

  const caption = document.createElement('caption');
  caption.textContent = '预算估算';
  table.appendChild(caption);

  const head = document.createElement('thead');
  const headRow = document.createElement('tr');
  for (const label of ['项目', '区间']) {
    const cell = document.createElement('th');
    cell.textContent = label;
    headRow.appendChild(cell);
  }
  head.appendChild(headRow);
  table.appendChild(head);

  const body = document.createElement('tbody');
  for (const [key, label] of Object.entries(BUDGET_LABELS)) {
    const range = budget && budget[key];
    if (!range) {
      continue;
    }
    const row = document.createElement('tr');
    if (key === 'total') {
      row.className = 'total-row';
    }
    const nameCell = document.createElement('td');
    nameCell.textContent = label;
    const valueCell = document.createElement('td');

    if (key === 'lodging' && itinerary.accommodation_status === 'unknown') {
      valueCell.textContent = '未查到参考价，未计入';
    } else if (
      key === 'lodging' &&
      itinerary.accommodation_status === 'not_needed'
    ) {
      valueCell.textContent = '不需要住宿';
    } else {
      valueCell.textContent = `${money(range.min)} – ${money(range.max)}`;
    }

    row.append(nameCell, valueCell);
    body.appendChild(row);
  }
  table.appendChild(body);

  if ((itinerary.ticket_unknown_count || 0) > 0) {
    const note = document.createElement('p');
    note.className = 'budget-note';
    note.textContent = `另有 ${itinerary.ticket_unknown_count} 个景点未查到票价，未计入门票预算。`;
    table.appendChild(note);
  }

  return table;
}
```

- [ ] **Step 4: 在 `renderItinerary` 中插入住宿区域并更新预算调用**

在每日行程循环之后、预算之前加入：

```javascript
  const accommodation = renderAccommodation(itinerary);
  if (accommodation) {
    els.itinerary.appendChild(accommodation);
  }
```

把 `els.itinerary.appendChild(renderBudget(itinerary.budget));` 改为：

```javascript
  if (itinerary.budget) {
    els.itinerary.appendChild(renderBudget(itinerary));
  }
```

- [ ] **Step 5: 追加 CSS**

```css
.accommodation-section {
  border-top: 1px solid var(--border);
  padding-top: 12px;
  margin-top: 4px;
}

.accommodation-section h2 {
  font-size: 1rem;
  margin: 0 0 8px;
}

.hotel-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 8px;
}

.hotel-card {
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 10px 12px;
  background: var(--panel-soft);
}

.hotel-card h4 {
  margin: 0 0 2px;
  font-size: 0.95rem;
}

.hotel-price {
  margin: 0 0 4px;
  color: var(--accent);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.hotel-card a {
  color: var(--primary);
  font-size: 0.8rem;
}

.accommodation-note,
.budget-note {
  margin: 8px 0 0;
  color: var(--muted);
  font-size: 0.78rem;
}

.ticket-note {
  margin: 2px 0 0;
  color: var(--muted);
  font-size: 0.78rem;
}
```

- [ ] **Step 6: 运行静态服务测试**

Run: `.\.venv\Scripts\python -m pytest tests/test_api.py -v`
Expected: 7 passed

- [ ] **Step 7: 浏览器手动验证**

启动服务后测试：

- 已知票价：活动显示 `门票 ¥60 – ¥60`，有「票价来源」
- 未知票价：显示 `票价未知，需官网确认`，预算下方提示未知名额
- 住宿：显示 2–3 家酒店卡片、每晚价格、来源
- 375px：无横向溢出

- [ ] **Step 8: 提交**

```bash
git add app/static/app.js app/static/style.css
git commit -m "feat: 前端展示真实票价与住宿参考"
```

---

## Task 8：端到端、文档与真实冒烟

**Files:**
- Modify: `tests/test_e2e.py`
- Modify: `README.md`
- Modify: `PROGRESS.md`

- [ ] **Step 1: 更新 `tests/test_e2e.py` 的 FakeTools**

导入并扩展：

```python
from app.agent.tools.lodging import LodgingResult
from app.agent.tools.tickets import TicketInfo
from app.schemas import HotelOption, CostRange
```

`FakeTools` 增加：

```python
    async def tickets(self, city, attractions):
        self.calls.append("tickets")
        return [
            TicketInfo(
                attraction="故宫",
                status="known",
                price=CostRange(min=60, max=60),
                note="门票 60 元",
                source_url="https://ticket.example.com",
            )
        ]

    async def lodging(self, city, accommodation, budget_level, start_date, nights, travelers):
        self.calls.append("lodging")
        return LodgingResult(
            status="known",
            hotels=[
                HotelOption(
                    name="测试酒店",
                    price_per_night=CostRange(min=400, max=600),
                    source_url="https://hotel.example.com",
                )
            ],
            nightly_range=CostRange(min=400, max=600),
            note="参考价，查询于 2026-11-07",
        )
```

把 `budget` 改为：

```python
    def budget(
        self,
        days,
        travelers,
        budget_level,
        ticket_total=0,
        city_tier=1,
        ticket_range=None,
        lodging_range=None,
    ):
        self.calls.append("budget")
        lodging = lodging_range or CostRange(min=800, max=1200)
        tickets = ticket_range or CostRange(min=60, max=60)
        return BudgetBreakdown(
            lodging=lodging,
            food=CostRange(min=450, max=900),
            local_transport=CostRange(min=90, max=180),
            tickets=tickets,
            total=CostRange(
                min=lodging.min + 450 + 90 + tickets.min,
                max=lodging.max + 900 + 180 + tickets.max,
            ),
        )
```

在构造 `ChatAgent` 时加入：

```python
        get_ticket_prices=tools.tickets,
        get_accommodation_options=tools.lodging,
```

更新断言：

```python
    assert itinerary["budget"]["lodging"] == {"min": 800, "max": 1200}
    assert itinerary["budget"]["tickets"] == {"min": 60, "max": 60}
    assert itinerary["budget"]["total"] == {"min": 1400, "max": 2340}
    assert itinerary["accommodation_status"] == "known"
    assert itinerary["accommodation_options"][0]["name"] == "测试酒店"
    assert itinerary["ticket_unknown_count"] == 0
    assert itinerary["day_plans"][0]["activities"][0]["ticket_status"] == "known"
    assert tools.calls == ["search", "tickets", "lodging", "weather", "budget"]
```

- [ ] **Step 2: 运行端到端测试**

Run: `.\.venv\Scripts\python -m pytest tests/test_e2e.py -v`
Expected: 1 passed

- [ ] **Step 3: 运行全量测试**

Run: `.\.venv\Scripts\python -m pytest -v`
Expected: 全部 PASS，无 warning

- [ ] **Step 4: 真实冒烟**

重启服务：

```powershell
.\.venv\Scripts\python -m uvicorn app.main:app --port 8000
```

输入：

```text
我想去北京玩三天，喜欢历史
```

然后：

```text
好的，开始规划
```

确认：
- 至少一个景点显示可追溯票价
- 住宿参考显示 2–3 家酒店
- 预算住宿行不再是固定 ¥800–¥1,400
- 预算门票行大于 0
- 未查到票价的景点有明确提示

- [ ] **Step 5: 更新 README**

在功能列表补充：

```markdown
- 真实景点票价：Tavily 查询 + LLM 抽取 + 证据校验，展示区间、来源与查询日期
- 真实住宿参考：2–3 家参考酒店，展示每晚价格区间与来源
- 票价/住宿未知时明确标注，不以 0 或固定数字冒充
```

在已知限制表格补充：

```markdown
| 票价与酒店价格非实时 | 与当日实际价格可能有差异 | 显示查询日期与来源，注明以官方/实际预订为准 |
| 住宿房间数按双人房估算 | 多人出行可能不准确 | 默认 `ceil(人数/2)` 间，后续可让用户选房型 |
| 境外景点/酒店币种 | 预算按人民币处理 | 非人民币来源直接标未知 |
```

- [ ] **Step 6: 更新 PROGRESS**

在已完成部分补充：

```markdown
### 8. 真实票价与住宿参考价（2026-11-07）

- [x] 逐景点并行 Tavily 查询 + 批量 LLM 抽取 + 证据校验
- [x] 票价状态：known / free / unknown
- [x] 真实住宿参考：2–3 家酒店，每晚区间、来源、查询日期
- [x] 预算按真实门票区间 × 人数、真实住宿区间 × 晚数 × 房间数
- [x] 未知不退回固定数字
- [x] 测试数量更新（新增 test_json_utils / test_tavily_utils / test_tickets / test_lodging）
```

- [ ] **Step 7: 提交**

```bash
git add tests/test_e2e.py README.md PROGRESS.md
git commit -m "test: 真实票价与住宿端到端覆盖，更新文档"
```

---

## 完成标准

- [ ] 全量测试通过，输出无 warning
- [ ] 真实北京冒烟：票价与住宿均来自可追溯来源
- [ ] 未知票价不显示 0，未知住宿不退回固定单价表
- [ ] 门票预算按人数累计，住宿预算按晚数 × 房间数累计
- [ ] 375px 布局无回归
