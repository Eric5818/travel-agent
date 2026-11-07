from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from pydantic import ValidationError

from app.agent.json_utils import parse_json_object
from app.agent.profile import TripProfile
from app.agent.prompts import (
    EXTRACT_SYSTEM_PROMPT,
    GENERATION_SYSTEM_PROMPT,
    REPAIR_PROMPT,
)
from app.agent.tools.attractions import (
    search_attractions as default_search_attractions,
)
from app.agent.tools.budget import estimate_budget as default_estimate_budget
from app.agent.tools.lodging import (
    LodgingResult,
    get_accommodation_options as default_get_accommodation_options,
)
from app.agent.tools.tickets import (
    TicketInfo,
    get_ticket_prices as default_get_ticket_prices,
)
from app.agent.tools.weather import get_weather as default_get_weather
from app.errors import ItineraryGenerationError, ToolError
from app.schemas import BudgetBreakdown, CostRange, Itinerary

MAX_TOOL_CALLS = 6

QUESTION_TEMPLATES = {
    "destination": "你想去哪里旅行？",
    "days": "计划玩几天？",
    "preferences": "你更喜欢哪类体验？自然风光、历史人文、亲子、美食、购物、休闲都可以。",
}


class LLM(Protocol):
    async def complete(self, messages: list[dict]) -> str: ...


@dataclass
class AgentTurn:
    reply: str
    profile: TripProfile
    itinerary: Itinerary | None = None
    error: str | None = None


class TooManyToolCalls(RuntimeError):
    pass


class ChatAgent:
    def __init__(
        self,
        llm: LLM,
        search_attractions=None,
        get_weather=None,
        estimate_budget=None,
        get_ticket_prices=None,
        get_accommodation_options=None,
        max_tool_calls: int = MAX_TOOL_CALLS,
    ):
        self.llm = llm
        self.search_attractions = search_attractions or default_search_attractions
        self.get_weather = get_weather or default_get_weather
        self.estimate_budget = estimate_budget or default_estimate_budget
        self.get_ticket_prices = (
            get_ticket_prices or self._default_ticket_prices
        )
        self.get_accommodation_options = (
            get_accommodation_options or self._default_accommodation_options
        )
        self.max_tool_calls = max_tool_calls
        self._tool_calls = 0

    async def _default_ticket_prices(self, city, attractions):
        return await default_get_ticket_prices(
            city, attractions, llm=self.llm
        )

    async def _default_accommodation_options(
        self, city, accommodation, budget_level, start_date, nights, travelers
    ):
        return await default_get_accommodation_options(
            city,
            accommodation,
            budget_level,
            start_date,
            nights,
            travelers,
            llm=self.llm,
        )

    async def handle(self, message: str, session) -> AgentTurn:
        self._tool_calls = 0
        profile = session.profile

        extraction = await self._extract(message, session.history)
        updates = dict(extraction or {})
        intent = updates.pop("intent", "chat")
        if updates:
            profile = profile.merge(updates)
        session.profile = profile
        session.history.append({"role": "user", "content": message})

        missing = profile.missing_required()
        if missing:
            reply = QUESTION_TEMPLATES[missing[0]]
            session.history.append({"role": "assistant", "content": reply})
            return AgentTurn(reply=reply, profile=profile)

        if intent != "plan":
            reply = self._confirmation(profile)
            session.history.append({"role": "assistant", "content": reply})
            return AgentTurn(reply=reply, profile=profile)

        session.state = "PLANNING"
        try:
            turn = await self._plan(profile, session)
        except ToolError as exc:
            reply = (
                f"暂时无法获取所需数据（{exc.kind}）：{exc.message}。"
                "我不会编造景点或天气信息，请稍后重试。"
            )
            session.history.append({"role": "assistant", "content": reply})
            return AgentTurn(reply=reply, profile=profile, error=exc.kind)
        except TooManyToolCalls:
            reply = (
                f"本轮工具调用次数已达上限（{self.max_tool_calls} 次），"
                "已停止规划。请重试或缩小行程范围。"
            )
            session.history.append({"role": "assistant", "content": reply})
            return AgentTurn(reply=reply, profile=profile, error="tool_limit")

        session.state = "COMPLETED"
        session.history.append({"role": "assistant", "content": turn.reply})
        return turn

    async def _extract(self, message: str, history: list[dict]) -> dict | None:
        messages = [{"role": "system", "content": EXTRACT_SYSTEM_PROMPT}]
        messages.extend(history[-20:])
        messages.append({"role": "user", "content": message})
        text = await self.llm.complete(messages)
        return parse_json_object(text)

    def _confirmation(self, profile: TripProfile) -> str:
        preferences = "、".join(profile.preferences)
        return (
            f"已了解：{profile.destination} {profile.days} 天，偏好{preferences}。"
            "要开始规划吗？"
        )

    def _consume_tool_call(self) -> None:
        self._tool_calls += 1
        if self._tool_calls > self.max_tool_calls:
            raise TooManyToolCalls

    async def _plan(self, profile: TripProfile, session) -> AgentTurn:
        city = profile.destination
        start_date = (
            profile.start_date.isoformat()
            if profile.start_date is not None
            else date.today().isoformat()
        )
        nights = profile.days - 1 if profile.days > 1 else 1

        self._consume_tool_call()
        attractions = await self.search_attractions(city, profile.preferences)

        ticket_infos: list[TicketInfo] = []
        if attractions:
            self._consume_tool_call()
            ticket_infos = await self.get_ticket_prices(city, attractions)

        if profile.accommodation == "不需要":
            lodging = LodgingResult(status="not_needed", note="不需要住宿")
        else:
            self._consume_tool_call()
            lodging = await self.get_accommodation_options(
                city,
                profile.accommodation,
                profile.budget_level,
                start_date,
                nights,
                profile.travelers,
            )

        self._consume_tool_call()
        weather = await self.get_weather(city, start_date, profile.days)

        rooms = max(1, math.ceil(profile.travelers / 2))
        if lodging.status == "known" and lodging.nightly_range is not None:
            lodging_range = CostRange(
                min=round(lodging.nightly_range.min * nights * rooms, 2),
                max=round(lodging.nightly_range.max * nights * rooms, 2),
            )
        else:
            lodging_range = CostRange(min=0, max=0)

        placeholder_budget = BudgetBreakdown(
            lodging=CostRange(min=0, max=0),
            food=CostRange(min=0, max=0),
            local_transport=CostRange(min=0, max=0),
            tickets=CostRange(min=0, max=0),
            total=CostRange(min=0, max=0),
        )

        itinerary = await self._generate_itinerary(
            profile, attractions, weather, placeholder_budget
        )

        unknown_count = self._apply_ticket_prices(itinerary, ticket_infos)
        ticket_range = self._ticket_range(
            itinerary, ticket_infos, profile.travelers
        )

        self._consume_tool_call()
        budget = self.estimate_budget(
            profile.days,
            profile.travelers,
            profile.budget_level,
            ticket_range=ticket_range,
            lodging_range=lodging_range,
        )
        itinerary.budget = budget

        itinerary.ticket_unknown_count = unknown_count
        itinerary.accommodation_options = lodging.hotels
        itinerary.accommodation_status = lodging.status
        itinerary.accommodation_note = lodging.note or None

        reply = (
            f"已为你生成{city}{profile.days}天的行程，"
            "包含每日安排、天气、票价和住宿参考。"
        )
        return AgentTurn(reply=reply, profile=profile, itinerary=itinerary)

    def _apply_ticket_prices(
        self, itinerary: Itinerary, ticket_infos: list[TicketInfo]
    ) -> int:
        by_name = {info.attraction: info for info in ticket_infos}
        unknown: set[str] = set()

        for day in itinerary.day_plans:
            for activity in day.activities:
                if activity.type != "attraction":
                    continue
                info = by_name.get(activity.name.strip())
                if info is None:
                    activity.ticket_status = "unknown"
                    activity.cost_estimate = None
                    activity.ticket_note = "未查到该景点票价，需官网确认"
                    unknown.add(activity.name)
                    continue
                if info.status == "free":
                    activity.ticket_status = "free"
                    activity.cost_estimate = CostRange(min=0, max=0)
                    activity.ticket_note = info.note
                    activity.ticket_source_url = info.source_url
                elif info.status == "known" and info.price is not None:
                    activity.ticket_status = "known"
                    activity.cost_estimate = info.price
                    activity.ticket_note = info.note
                    activity.ticket_source_url = info.source_url
                else:
                    activity.ticket_status = "unknown"
                    activity.cost_estimate = None
                    activity.ticket_note = (
                        info.note or "票价未知，需官网确认"
                    )
                    activity.ticket_source_url = info.source_url
                    unknown.add(activity.name)

        return len(unknown)

    def _ticket_range(
        self,
        itinerary: Itinerary,
        ticket_infos: list[TicketInfo],
        travelers: int,
    ) -> CostRange:
        by_name = {
            info.attraction: info
            for info in ticket_infos
            if info.status in {"known", "free"} and info.price is not None
        }
        used: dict[str, CostRange] = {}
        for day in itinerary.day_plans:
            for activity in day.activities:
                if activity.type != "attraction":
                    continue
                info = by_name.get(activity.name.strip())
                if info is not None and info.price is not None:
                    used[activity.name] = info.price

        if not used:
            return CostRange(min=0, max=0)

        minimum = sum(price.min for price in used.values()) * travelers
        maximum = sum(price.max for price in used.values()) * travelers
        return CostRange(min=round(minimum, 2), max=round(maximum, 2))

    async def _generate_itinerary(
        self, profile: TripProfile, attractions, weather, budget
    ) -> Itinerary:
        context = {
            "city": profile.destination,
            "days": profile.days,
            "travelers": profile.travelers,
            "preferences": profile.preferences,
            "budget_level": profile.budget_level,
            "accommodation": profile.accommodation,
            "start_date": (
                profile.start_date.isoformat()
                if profile.start_date is not None
                else None
            ),
            "attractions": [
                item.model_dump() if hasattr(item, "model_dump") else item
                for item in attractions
            ],
            "weather": [
                item.model_dump() if hasattr(item, "model_dump") else item
                for item in weather
            ],
            "budget": budget.model_dump(),
        }
        base_messages = [
            {"role": "system", "content": GENERATION_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
        ]

        last_text = ""
        last_error = ""
        for attempt in range(2):
            if attempt == 0:
                messages = base_messages
            else:
                messages = base_messages + [
                    {"role": "assistant", "content": last_text},
                    {
                        "role": "user",
                        "content": REPAIR_PROMPT.format(error=last_error),
                    },
                ]

            last_text = await self.llm.complete(messages)
            payload = parse_json_object(last_text)
            if payload is None:
                last_error = "返回内容不是合法的 JSON 对象"
                continue

            try:
                return self._to_itinerary(payload, profile, budget)
            except ValidationError as exc:
                last_error = str(exc)

        raise ItineraryGenerationError(
            f"行程 JSON 连续两次不合法：{last_error}"
        )

    def _to_itinerary(
        self, payload: dict, profile: TripProfile, budget
    ) -> Itinerary:
        data = dict(payload)
        data["city"] = profile.destination
        data["days"] = profile.days
        data["travelers"] = profile.travelers
        data["start_date"] = (
            profile.start_date.isoformat()
            if profile.start_date is not None
            else None
        )
        data["budget"] = budget.model_dump()
        data["data_sources"] = ["tavily", "wttr.in", "estimate"]
        data.setdefault("tips", [])
        return Itinerary.model_validate(data)
