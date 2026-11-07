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
