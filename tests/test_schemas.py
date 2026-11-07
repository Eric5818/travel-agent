from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas import (
    Activity,
    BudgetBreakdown,
    CostRange,
    DayPlan,
    Itinerary,
    WeatherInfo,
)


def make_itinerary(**overrides) -> Itinerary:
    data = {
        "city": "北京",
        "start_date": date(2026, 11, 20),
        "days": 1,
        "travelers": 2,
        "summary": "历史人文一日游",
        "day_plans": [
            DayPlan(
                date="2026-11-20",
                day_index=1,
                theme="历史人文",
                weather=WeatherInfo(
                    date="2026-11-20",
                    weather_desc="晴",
                    temp_high_c=10,
                    temp_low_c=2,
                    chance_of_rain=0,
                    suggestion="注意保暖",
                    unavailable=False,
                ),
                activities=[
                    Activity(
                        time="09:00",
                        name="故宫",
                        type="attraction",
                        duration_min=180,
                        description="参观紫禁城",
                        location_hint="东城区",
                        cost_estimate=CostRange(min=60, max=60),
                        source_url="https://example.com/gugong",
                    )
                ],
                accommodation="酒店",
                daily_cost=CostRange(min=300, max=500),
            )
        ],
        "budget": BudgetBreakdown(
            lodging=CostRange(min=300, max=500),
            food=CostRange(min=100, max=200),
            local_transport=CostRange(min=20, max=50),
            tickets=CostRange(min=60, max=60),
            total=CostRange(min=480, max=810),
        ),
        "tips": ["提前预约故宫门票"],
        "data_sources": ["tavily", "wttr.in", "estimate"],
    }
    data.update(overrides)
    return Itinerary(**data)


def test_cost_range_rejects_min_greater_than_max():
    with pytest.raises(ValidationError):
        CostRange(min=100, max=50)


def test_itinerary_round_trips():
    itinerary = make_itinerary()

    dumped = itinerary.model_dump(mode="json")
    restored = Itinerary.model_validate(dumped)

    assert restored == itinerary


def test_data_sources_rejects_unknown_source():
    with pytest.raises(ValidationError):
        make_itinerary(data_sources=["tavily", "google"])
