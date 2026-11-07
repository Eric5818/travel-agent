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
        "北京",
        [attraction("故宫"), attraction("天坛"), attraction("颐和园")],
        llm,
        client=client,
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

    result = await get_ticket_prices(
        "北京", [attraction("故宫")], llm, client=client
    )

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

    result = await get_ticket_prices(
        "北京", [attraction("故宫")], llm, client=client
    )

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

    result = await get_ticket_prices(
        "北京", [attraction("故宫")], llm, client=client
    )

    assert result[0].status == "known"
    assert llm.calls == 2


@pytest.mark.asyncio
async def test_invalid_json_twice_marks_unknown():
    llm = FakeLLM(["not json", "still not json"])
    client = FakeTavily({"故宫": payload("故宫门票 60 元", "https://a", "60 元")})

    result = await get_ticket_prices(
        "北京", [attraction("故宫")], llm, client=client
    )

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


def test_ticket_info_model():
    info = TicketInfo(attraction="故宫", status="known")
    assert info.price is None
