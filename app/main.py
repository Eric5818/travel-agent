from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Iterator

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.agent.chat_agent import AgentTurn, ChatAgent
from app.agent.tools.attractions import search_attractions
from app.agent.tools.weather import get_weather
from app.config import ConfigError, Settings, load
from app.session import SessionStore

STATIC_DIR = Path(__file__).resolve().parent / "static"
_UNSET = object()


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class DeepSeekLLM:
    def __init__(self, settings: Settings):
        from openai import OpenAI

        self._client = OpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )
        self._model = settings.deepseek_model

    async def complete(self, messages: list[dict]) -> str:
        response = await asyncio.to_thread(
            self._client.chat.completions.create,
            model=self._model,
            messages=messages,
            temperature=0.3,
        )
        return response.choices[0].message.content or ""


def _build_default_agent(settings: Settings) -> ChatAgent:
    async def search(city: str, keywords: list[str], limit: int = 8):
        return await search_attractions(
            city, keywords, limit=limit, api_key=settings.tavily_api_key
        )

    async def weather(city: str, start_date: str, days: int):
        return await get_weather(
            city, start_date, days, base_url=settings.weather_base_url
        )

    return ChatAgent(
        llm=DeepSeekLLM(settings),
        search_attractions=search,
        get_weather=weather,
    )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _chunks(text: str, size: int = 12) -> Iterator[str]:
    for index in range(0, len(text), size):
        yield text[index : index + size]


def create_app(
    agent=_UNSET,
    settings=_UNSET,
    session_store: SessionStore | None = None,
) -> FastAPI:
    app = FastAPI(title="智能旅游推荐助手")
    store = session_store or SessionStore()
    app.state.session_store = store

    config_error: str | None = None
    if settings is _UNSET:
        try:
            settings = load()
        except ConfigError as exc:
            config_error = str(exc)
            settings = None
    app.state.settings = settings
    app.state.config_error = config_error

    if agent is _UNSET:
        agent = _build_default_agent(settings) if settings is not None else None
    app.state.agent = agent

    @app.post("/api/session")
    async def create_session():
        session = store.create()
        return {"session_id": session.session_id}

    @app.get("/api/health")
    async def health():
        llm_ok = app.state.agent is not None
        tavily_ok = settings is not None and settings.tavily_configured
        degraded = (
            not llm_ok
            or settings is None
            or settings.degraded
            or config_error is not None
        )
        return {
            "llm": "ok" if llm_ok else "missing",
            "tavily": "ok" if tavily_ok else "missing",
            "weather": "ok",
            "degraded": degraded,
            "config_error": config_error,
        }

    @app.post("/api/chat")
    async def chat(payload: ChatRequest):
        if app.state.agent is None:
            raise HTTPException(status_code=503, detail="LLM 未配置")

        session = store.get_or_create(payload.session_id)
        async with store.lock(session.session_id):
            try:
                turn = await app.state.agent.handle(payload.message, session)
            except Exception as exc:  # noqa: BLE001 - API 边界转为可读错误
                turn = AgentTurn(
                    reply=f"本轮处理失败：{exc}",
                    profile=session.profile,
                    error="agent_error",
                )

        async def event_stream():
            yield _sse("session", {"session_id": session.session_id})
            yield _sse("profile", turn.profile.model_dump(mode="json"))
            if turn.itinerary is not None:
                yield _sse(
                    "itinerary", turn.itinerary.model_dump(mode="json")
                )
            if turn.error:
                yield _sse(
                    "error", {"kind": turn.error, "message": turn.reply}
                )
            for chunk in _chunks(turn.reply):
                yield _sse("token", {"text": chunk})
            yield _sse("done", {})

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    if STATIC_DIR.exists():
        app.mount(
            "/static", StaticFiles(directory=STATIC_DIR), name="static"
        )

        @app.get("/")
        async def index():
            return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_app()
