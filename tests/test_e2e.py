import json

from fastapi.testclient import TestClient

from app.agent.chat_agent import ChatAgent
from app.agent.tools.lodging import LodgingResult
from app.agent.tools.tickets import TicketInfo
from app.main import create_app
from app.schemas import (
    Attraction,
    BudgetBreakdown,
    CostRange,
    HotelOption,
    WeatherInfo,
)


class FakeLLM:
    def __init__(self, responses):
        self._responses = list(responses)

    async def complete(self, messages):
        return self._responses.pop(0)


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
        },
        "activities": [
            {
                "time": "09:00",
                "name": "故宫",
                "type": "attraction",
                "duration_min": 180,
                "description": "参观故宫",
                "cost_estimate": {"min": 60, "max": 60},
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


class FakeTools:
    def __init__(self):
        self.calls = []

    async def search(self, city, keywords, limit=8):
        self.calls.append("search")
        return [
            Attraction(
                name="故宫",
                category="历史",
                description="明清皇宫",
                source_url="https://example.com/gugong",
            )
        ]

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

    async def lodging(
        self, city, accommodation, budget_level, start_date, nights, travelers
    ):
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

    async def weather(self, city, start_date, days):
        self.calls.append("weather")
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


def parse_sse(text: str):
    events = []
    for block in text.strip().split("\n\n"):
        if not block.strip():
            continue
        lines = block.splitlines()
        event = next(
            line[len("event: ") :] for line in lines if line.startswith("event: ")
        )
        data = next(
            line[len("data: ") :] for line in lines if line.startswith("data: ")
        )
        events.append((event, json.loads(data)))
    return events


def test_full_conversation_collecting_to_completed():
    llm = FakeLLM(
        [
            extraction(destination="北京", days=3, preferences=["历史"]),
            extraction(intent="plan"),
            json.dumps(GOOD_ITINERARY, ensure_ascii=False),
        ]
    )
    tools = FakeTools()
    agent = ChatAgent(
        llm=llm,
        search_attractions=tools.search,
        get_ticket_prices=tools.tickets,
        get_accommodation_options=tools.lodging,
        get_weather=tools.weather,
        estimate_budget=tools.budget,
    )
    app = create_app(agent=agent, settings=None)
    client = TestClient(app)
    session_id = client.post("/api/session").json()["session_id"]

    first = client.post(
        "/api/chat",
        json={"message": "我想去北京玩三天，喜欢历史", "session_id": session_id},
    )
    first_events = parse_sse(first.text)
    first_text = "".join(
        data["text"] for name, data in first_events if name == "token"
    )
    assert "开始规划吗" in first_text
    session = app.state.session_store.get(session_id)
    assert session.state == "COLLECTING"
    assert session.profile.destination == "北京"
    assert session.profile.days == 3
    profile_event = next(
        data for name, data in first_events if name == "profile"
    )
    assert profile_event["destination"] == "北京"

    second = client.post(
        "/api/chat",
        json={"message": "好的，开始规划", "session_id": session_id},
    )
    second_events = parse_sse(second.text)
    names = [name for name, _ in second_events]
    assert "itinerary" in names
    assert names[-1] == "done"

    itinerary = next(
        data for name, data in second_events if name == "itinerary"
    )
    assert itinerary["city"] == "北京"
    assert itinerary["days"] == 3
    assert len(itinerary["day_plans"]) == 3
    assert itinerary["data_sources"] == ["tavily", "wttr.in", "estimate"]
    assert itinerary["budget"]["lodging"] == {"min": 800, "max": 1200}
    assert itinerary["budget"]["tickets"] == {"min": 60, "max": 60}
    assert itinerary["budget"]["total"] == {"min": 1400, "max": 2340}
    assert itinerary["accommodation_status"] == "known"
    assert itinerary["accommodation_options"][0]["name"] == "测试酒店"
    assert itinerary["ticket_unknown_count"] == 0
    assert itinerary["day_plans"][0]["activities"][0]["ticket_status"] == "known"

    assert app.state.session_store.get(session_id).state == "COMPLETED"
    assert tools.calls == [
        "search",
        "tickets",
        "lodging",
        "weather",
        "budget",
    ]
