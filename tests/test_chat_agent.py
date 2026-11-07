import json
from dataclasses import dataclass, field

import pytest

from app.agent.chat_agent import ChatAgent
from app.agent.profile import TripProfile
from app.agent.tools.lodging import LodgingResult
from app.agent.tools.tickets import TicketInfo
from app.errors import ItineraryGenerationError, ToolError
from app.schemas import (
    Attraction,
    BudgetBreakdown,
    CostRange,
    HotelOption,
    WeatherInfo,
)


def extraction(**overrides) -> str:
    payload = {"intent": "chat"}
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


def day_plan(index: int) -> dict:
    return {
        "date": f"2026-11-{19 + index}",
        "day_index": index,
        "theme": "历史人文",
        "weather": {
            "date": f"2026-11-{19 + index}",
            "weather_desc": "晴",
            "temp_high_c": 10,
            "temp_low_c": 2,
            "chance_of_rain": 0,
            "suggestion": "注意保暖",
            "unavailable": False,
        },
        "activities": [
            {
                "time": "09:00",
                "name": "故宫",
                "type": "attraction",
                "duration_min": 180,
                "description": "参观故宫",
                "cost_estimate": {"min": 60, "max": 60},
                "source_url": "https://example.com/gugong",
            }
        ],
        "accommodation": "酒店",
        "daily_cost": {"min": 300, "max": 500},
    }


GOOD_ITINERARY = {
    "summary": "北京三日历史人文之旅",
    "day_plans": [day_plan(1), day_plan(2), day_plan(3)],
    "tips": ["提前预约故宫门票"],
    "data_sources": ["tavily", "wttr.in", "estimate"],
}


class FakeLLM:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    async def complete(self, messages):
        self.calls.append(messages)
        return self._responses.pop(0)


@dataclass
class FakeSession:
    history: list = field(default_factory=list)
    profile: TripProfile = field(default_factory=TripProfile)
    state: str = "COLLECTING"


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
        self.ticket_names: list[str] = []
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
        self.ticket_names = [item.name for item in attractions]
        return self.ticket_infos

    async def lodging(
        self, city, accommodation, budget_level, start_date, nights, travelers
    ):
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


@pytest.mark.asyncio
async def test_first_turn_asks_only_for_days():
    llm = FakeLLM([extraction(destination="北京")])
    agent, _ = make_agent(llm)
    session = FakeSession()

    turn = await agent.handle("北京", session)

    assert turn.profile.destination == "北京"
    assert "几天" in turn.reply
    assert turn.reply.count("？") == 1
    assert turn.itinerary is None


@pytest.mark.asyncio
async def test_complete_slots_without_confirmation_asks_to_plan():
    llm = FakeLLM(
        [extraction(destination="北京", days=3, preferences=["历史"])]
    )
    agent, _ = make_agent(llm)
    session = FakeSession()

    turn = await agent.handle("北京三天，喜欢历史", session)

    assert "开始规划吗" in turn.reply
    assert turn.itinerary is None


@pytest.mark.asyncio
async def test_confirmed_plan_calls_tools_and_returns_itinerary():
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
    agent, tools = make_agent(llm)
    session = FakeSession()

    turn = await agent.handle("好的，开始规划", session)

    assert turn.itinerary is not None
    assert turn.itinerary.city == "北京"
    assert turn.itinerary.days == 3
    assert turn.itinerary.travelers == 1
    assert turn.error is None
    assert tools.calls == {
        "search": 1,
        "tickets": 1,
        "lodging": 1,
        "weather": 1,
        "budget": 1,
    }
    assert session.state == "COMPLETED"


@pytest.mark.asyncio
async def test_tool_error_is_relayed_without_fabricating():
    tools = FakeTools(search_error=ToolError("tavily_unavailable", "搜索超时"))
    llm = FakeLLM(
        [
            extraction(
                destination="北京",
                days=3,
                preferences=["历史"],
                intent="plan",
            )
        ]
    )
    agent, _ = make_agent(llm, tools=tools)
    session = FakeSession()

    turn = await agent.handle("开始规划", session)

    assert turn.itinerary is None
    assert turn.error == "tavily_unavailable"
    assert "无法获取" in turn.reply
    assert "不会编造" in turn.reply
    assert "故宫" not in turn.reply


@pytest.mark.asyncio
async def test_invalid_itinerary_json_is_repaired_once():
    llm = FakeLLM(
        [
            extraction(
                destination="北京",
                days=3,
                preferences=["历史"],
                intent="plan",
            ),
            "这不是 JSON",
            json.dumps(GOOD_ITINERARY, ensure_ascii=False),
        ]
    )
    agent, _ = make_agent(llm)
    session = FakeSession()

    turn = await agent.handle("开始规划", session)

    assert turn.itinerary is not None
    assert len(llm.calls) == 3


@pytest.mark.asyncio
async def test_invalid_itinerary_json_twice_raises():
    llm = FakeLLM(
        [
            extraction(
                destination="北京",
                days=3,
                preferences=["历史"],
                intent="plan",
            ),
            "这不是 JSON",
            "仍然不是 JSON",
        ]
    )
    agent, _ = make_agent(llm)
    session = FakeSession()

    with pytest.raises(ItineraryGenerationError):
        await agent.handle("开始规划", session)


@pytest.mark.asyncio
async def test_tool_call_limit_aborts_planning():
    llm = FakeLLM(
        [
            extraction(
                destination="北京",
                days=3,
                preferences=["历史"],
                intent="plan",
            )
        ]
    )
    agent, _ = make_agent(llm, max_tool_calls=2)
    session = FakeSession()

    turn = await agent.handle("开始规划", session)

    assert turn.itinerary is None
    assert turn.error == "tool_limit"
    assert "上限" in turn.reply


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
        attractions=[
            Attraction(
                name="北京十大歷史人文景點｜故宮長城頤和園等經典文化地標攻略",
                category="历史",
            )
        ],
        ticket_infos=[known_ticket()],
        lodging_result=known_lodging(),
    )
    agent, _ = make_agent(llm, tools=tools)
    session = FakeSession()

    turn = await agent.handle("开始规划", session)

    itinerary = turn.itinerary
    assert itinerary is not None
    assert tools.ticket_names == ["故宫"]
    activity = itinerary.day_plans[0].activities[0]
    assert activity.ticket_status == "known"
    assert activity.cost_estimate == CostRange(min=60, max=60)
    assert itinerary.ticket_unknown_count == 0
    assert itinerary.budget.lodging == CostRange(min=800, max=1200)
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
