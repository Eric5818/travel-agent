import json
from pathlib import Path

import httpx
import pytest

from app.agent.tools.weather import get_weather
from app.errors import ToolError

FIXTURE = Path(__file__).parent / "fixtures" / "weather_j1.json"


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self, payload=None, exc=None):
        self._payload = payload
        self._exc = exc

    async def get(self, url, **kwargs):
        if self._exc is not None:
            raise self._exc
        return FakeResponse(self._payload)


def load_fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_parses_three_forecast_days():
    client = FakeClient(load_fixture())

    weather = await get_weather("北京", "2026-11-20", 3, client=client)

    assert len(weather) == 3
    assert [item.date for item in weather] == [
        "2026-11-20",
        "2026-11-21",
        "2026-11-22",
    ]
    assert all(not item.unavailable for item in weather)
    assert weather[0].weather_desc == "晴"
    assert weather[0].temp_high_c == 10.0
    assert weather[0].temp_low_c == 2.0
    assert weather[0].chance_of_rain == 0
    assert weather[1].chance_of_rain == 60


@pytest.mark.asyncio
async def test_days_beyond_forecast_marked_unavailable():
    client = FakeClient(load_fixture())

    weather = await get_weather("北京", "2026-11-20", 5, client=client)

    assert len(weather) == 5
    assert all(not item.unavailable for item in weather[:3])
    assert all(item.unavailable for item in weather[3:])
    assert [item.date for item in weather[3:]] == ["2026-11-23", "2026-11-24"]
    assert weather[3].temp_high_c is None
    assert weather[3].weather_desc == "暂无预报"


@pytest.mark.asyncio
async def test_network_error_raises_typed_tool_error():
    client = FakeClient(exc=httpx.ConnectError("boom"))

    with pytest.raises(ToolError) as exc_info:
        await get_weather("北京", "2026-11-20", 3, client=client)

    assert exc_info.value.kind == "weather_unavailable"
