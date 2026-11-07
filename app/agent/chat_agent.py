from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from pydantic import ValidationError

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
from app.agent.tools.weather import get_weather as default_get_weather
from app.errors import ItineraryGenerationError, ToolError
from app.schemas import Itinerary

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


def _parse_json_object(text: str) -> dict | None:
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned[:4].lower() == "json":
            cleaned = cleaned[4:].strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        payload = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


class ChatAgent:
    def __init__(
        self,
        llm: LLM,
        search_attractions=None,
        get_weather=None,
        estimate_budget=None,
        max_tool_calls: int = MAX_TOOL_CALLS,
    ):
        self.llm = llm
        self.search_attractions = search_attractions or default_search_attractions
        self.get_weather = get_weather or default_get_weather
        self.estimate_budget = estimate_budget or default_estimate_budget
        self.max_tool_calls = max_tool_calls
        self._tool_calls = 0

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
        return _parse_json_object(text)

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

        self._consume_tool_call()
        attractions = await self.search_attractions(city, profile.preferences)

        self._consume_tool_call()
        weather = await self.get_weather(city, start_date, profile.days)

        self._consume_tool_call()
        budget = self.estimate_budget(
            profile.days, profile.travelers, profile.budget_level
        )

        itinerary = await self._generate_itinerary(
            profile, attractions, weather, budget
        )
        reply = (
            f"已为你生成{city}{profile.days}天的行程，"
            "包含每日安排、天气和预算估算。"
        )
        return AgentTurn(reply=reply, profile=profile, itinerary=itinerary)

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
            payload = _parse_json_object(last_text)
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
