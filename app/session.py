from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from app.agent.profile import TripProfile

DEFAULT_MAX_HISTORY = 40


class History(list):
    """List that keeps at most ``maxlen`` messages, dropping the oldest."""

    def __init__(self, maxlen: int = DEFAULT_MAX_HISTORY, items=()):
        super().__init__(items)
        self.maxlen = maxlen

    def append(self, item: Any) -> None:
        super().append(item)
        excess = len(self) - self.maxlen
        if excess > 0:
            del self[:excess]


@dataclass
class Session:
    session_id: str
    history: History = field(default_factory=History)
    profile: TripProfile = field(default_factory=TripProfile)
    state: str = "COLLECTING"
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class SessionStore:
    def __init__(self, max_history: int = DEFAULT_MAX_HISTORY):
        self.max_history = max_history
        self._sessions: dict[str, Session] = {}

    def create(self, session_id: str | None = None) -> Session:
        sid = session_id or uuid4().hex
        session = Session(
            session_id=sid, history=History(maxlen=self.max_history)
        )
        self._sessions[sid] = session
        return session

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def get_or_create(self, session_id: str | None = None) -> Session:
        if session_id:
            existing = self._sessions.get(session_id)
            if existing is not None:
                return existing
        return self.create(session_id)

    def lock(self, session_id: str) -> asyncio.Lock:
        return self.get_or_create(session_id).lock

    async def append(self, session: Session, role: str, content: str) -> None:
        async with session.lock:
            session.history.append({"role": role, "content": content})
