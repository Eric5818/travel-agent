import asyncio

import pytest

from app.session import SessionStore


def test_create_and_get_session():
    store = SessionStore()

    session = store.create()

    assert session.session_id
    assert store.get(session.session_id) is session
    assert store.get("missing") is None


def test_create_generates_unique_ids():
    store = SessionStore()

    first = store.create()
    second = store.create()

    assert first.session_id != second.session_id


def test_get_or_create_unknown_id_creates_session():
    store = SessionStore()

    session = store.get_or_create("abc123")

    assert session.session_id == "abc123"
    assert store.get("abc123") is session


@pytest.mark.asyncio
async def test_history_is_trimmed_to_40():
    store = SessionStore()
    session = store.create()

    for index in range(45):
        await store.append(session, "user", f"msg-{index}")

    assert len(session.history) == 40
    assert session.history[0]["content"] == "msg-5"
    assert session.history[-1]["content"] == "msg-44"


@pytest.mark.asyncio
async def test_lock_serializes_concurrent_access():
    store = SessionStore()
    session = store.create()
    order = []

    async def task(name: str, delay: float):
        async with store.lock(session.session_id):
            order.append(f"{name}:start")
            await asyncio.sleep(delay)
            order.append(f"{name}:end")

    await asyncio.gather(task("a", 0.02), task("b", 0))

    assert order == ["a:start", "a:end", "b:start", "b:end"]
