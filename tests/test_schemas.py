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
