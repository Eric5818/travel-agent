import json

from fastapi.testclient import TestClient

from app.agent.chat_agent import AgentTurn
from app.config import Settings
from app.main import create_app


class FakeAgent:
    def __init__(self, reply="你好，我是旅行助手。", itinerary=None, error=None):
        self.reply = reply
        self.itinerary = itinerary
        self.error = error
        self.messages = []

    async def handle(self, message, session):
        self.messages.append(message)
        session.history.append({"role": "user", "content": message})
        session.history.append({"role": "assistant", "content": self.reply})
        return AgentTurn(
            reply=self.reply,
            profile=session.profile,
            itinerary=self.itinerary,
            error=self.error,
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


def test_create_session_returns_id():
    app = create_app(agent=FakeAgent(), settings=None)
    client = TestClient(app)

    response = client.post("/api/session")

    assert response.status_code == 200
    session_id = response.json()["session_id"]
    assert session_id
    assert app.state.session_store.get(session_id) is not None


def test_chat_streams_profile_tokens_and_done():
    app = create_app(agent=FakeAgent(reply="北京三天"), settings=None)
    client = TestClient(app)

    response = client.post("/api/chat", json={"message": "我想去北京"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    events = parse_sse(response.text)
    names = [name for name, _ in events]
    assert names[0] == "session"
    assert [name for name in names if name in {"profile", "token", "done"}] == [
        "profile",
        "token",
        "done",
    ]

    tokens = "".join(data["text"] for name, data in events if name == "token")
    assert tokens == "北京三天"
    assert events[-1][0] == "done"


def test_chat_without_session_id_creates_session():
    app = create_app(agent=FakeAgent(), settings=None)
    client = TestClient(app)

    response = client.post("/api/chat", json={"message": "你好"})

    events = parse_sse(response.text)
    session_event = events[0]
    assert session_event[0] == "session"
    session_id = session_event[1]["session_id"]
    assert session_id
    assert app.state.session_store.get(session_id) is not None


def test_chat_reuses_existing_session():
    agent = FakeAgent()
    app = create_app(agent=agent, settings=None)
    client = TestClient(app)

    session_id = client.post("/api/session").json()["session_id"]
    client.post(
        "/api/chat",
        json={"message": "第一句", "session_id": session_id},
    )
    client.post(
        "/api/chat",
        json={"message": "第二句", "session_id": session_id},
    )

    session = app.state.session_store.get(session_id)
    user_messages = [
        item["content"] for item in session.history if item["role"] == "user"
    ]
    assert user_messages == ["第一句", "第二句"]
    assert agent.messages == ["第一句", "第二句"]


def test_health_reports_dependencies():
    settings = Settings(
        deepseek_api_key="sk-test", tavily_api_key="tvly-test"
    )
    app = create_app(agent=FakeAgent(), settings=settings)
    client = TestClient(app)

    data = client.get("/api/health").json()

    assert data["llm"] == "ok"
    assert data["tavily"] == "ok"
    assert data["weather"] == "ok"
    assert data["degraded"] is False


def test_root_serves_chat_page():
    app = create_app(agent=FakeAgent(), settings=None)
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "旅游推荐助手" in response.text
    assert 'id="chat"' in response.text


def test_static_assets_are_served():
    app = create_app(agent=FakeAgent(), settings=None)
    client = TestClient(app)

    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/style.css").status_code == 200
