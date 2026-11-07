import json

import pytest

from app.agent.tools.lodging import get_accommodation_options


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
