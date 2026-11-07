import asyncio

import pytest

from app.agent.tools.attractions import search_attractions
from app.errors import ToolError
from app.schemas import Attraction

STANDARD_PAYLOAD = {
    "answer": "北京历史文化景点推荐",
    "results": [
        {
            "title": "故宫博物院",
            "url": "https://example.com/gugong",
            "content": "明清两代皇宫，世界文化遗产。",
            "score": 0.95,
        },
        {
            "title": "天坛公园",
            "url": "https://example.com/tiantan",
            "content": "明清皇帝祭天祈谷的场所。",
            "score": 0.9,
        },
        {
            "title": "颐和园",
            "url": "https://example.com/yiheyuan",
            "content": "皇家园林，以昆明湖和万寿山著称。",
            "score": 0.85,
        },
    ],
}


class FakeTavilyClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.queries = []

    def search(self, query, **kwargs):
        self.queries.append(query)
        item = self._responses.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


@pytest.mark.asyncio
async def test_maps_tavily_response_to_attractions():
    client = FakeTavilyClient([STANDARD_PAYLOAD])

    result = await search_attractions("北京", ["历史"], limit=2, client=client)

    assert len(result) == 2
    assert all(isinstance(item, Attraction) for item in result)
    assert result[0].name == "故宫博物院"
    assert result[0].category == "历史"
    assert result[0].description == "明清两代皇宫，世界文化遗产。"
    assert result[0].source_url == "https://example.com/gugong"
    assert "北京" in client.queries[0]
    assert "历史" in client.queries[0]


@pytest.mark.asyncio
async def test_missing_api_key_raises_not_configured(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    with pytest.raises(ToolError) as exc_info:
        await search_attractions("北京", ["历史"])

    assert exc_info.value.kind == "tavily_not_configured"


@pytest.mark.asyncio
async def test_retries_once_after_timeout():
    client = FakeTavilyClient([asyncio.TimeoutError("slow"), STANDARD_PAYLOAD])

    result = await search_attractions("北京", ["历史"], limit=1, client=client)

    assert len(result) == 1
    assert len(client.queries) == 2


@pytest.mark.asyncio
async def test_two_timeouts_raise_unavailable():
    client = FakeTavilyClient(
        [asyncio.TimeoutError("slow"), asyncio.TimeoutError("slow")]
    )

    with pytest.raises(ToolError) as exc_info:
        await search_attractions("北京", ["历史"], client=client)

    assert exc_info.value.kind == "tavily_unavailable"
