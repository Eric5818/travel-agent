from __future__ import annotations

from datetime import date, timedelta
from urllib.parse import quote

import httpx

from app.errors import ToolError
from app.schemas import WeatherInfo

DEFAULT_WEATHER_BASE_URL = "https://wttr.in"
REQUEST_TIMEOUT = 15.0


def _build_suggestion(
    temp_high: float | None, temp_low: float | None, rain: int | None
) -> str:
    if rain is not None and rain >= 50:
        return "有降雨可能，建议带伞"
    if temp_high is not None and temp_high >= 30:
        return "气温较高，注意防晒补水"
    if temp_low is not None and temp_low <= 5:
        return "气温较低，注意保暖"
    return "天气适合出行"


def _parse_day(raw: dict) -> WeatherInfo:
    hourly = raw.get("hourly") or []
    if hourly:
        sample = hourly[4] if len(hourly) > 4 else hourly[len(hourly) // 2]
        desc_blocks = sample.get("weatherDesc") or [{"value": "未知"}]
        weather_desc = desc_blocks[0].get("value", "未知")
        chance_of_rain = int(float(sample.get("chanceofrain", 0)))
    else:
        weather_desc = "未知"
        chance_of_rain = 0

    temp_high = float(raw.get("maxtempC", 0))
    temp_low = float(raw.get("mintempC", 0))

    return WeatherInfo(
        date=raw["date"],
        weather_desc=weather_desc,
        temp_high_c=temp_high,
        temp_low_c=temp_low,
        chance_of_rain=max(0, min(100, chance_of_rain)),
        suggestion=_build_suggestion(temp_high, temp_low, chance_of_rain),
        unavailable=False,
    )


def _unavailable(day: date) -> WeatherInfo:
    return WeatherInfo(
        date=day.isoformat(),
        weather_desc="暂无预报",
        suggestion="出行前请复查天气",
        unavailable=True,
    )


async def get_weather(
    city: str,
    start_date: str,
    days: int,
    client: httpx.AsyncClient | None = None,
    base_url: str = DEFAULT_WEATHER_BASE_URL,
) -> list[WeatherInfo]:
    if days <= 0:
        return []

    url = f"{base_url.rstrip('/')}/{quote(city)}?format=j1"
    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)

    try:
        response = await client.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise ToolError(
            "weather_unavailable", f"无法获取 {city} 的天气数据：{exc}"
        ) from exc
    finally:
        if owns_client:
            await client.aclose()

    forecast = {
        raw.get("date"): raw for raw in payload.get("weather") or []
    }
    start = date.fromisoformat(start_date)

    result: list[WeatherInfo] = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        raw = forecast.get(day.isoformat())
        result.append(_parse_day(raw) if raw else _unavailable(day))
    return result
