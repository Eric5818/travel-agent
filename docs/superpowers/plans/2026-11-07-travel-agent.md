# 智能旅游推荐助手 实现计划

> **执行方式：** 同会话 inline TDD（本计划由实现者直接执行；不派 subagent）。每个任务先写失败测试，再写最小实现，测试通过后提交。

**Goal:** 交付一个本地运行的多轮聊天式旅游助手，能收集槽位、调用真实数据源并生成可校验的每日行程。

**Architecture:** FastAPI 托管零构建前端；`ChatAgent` 维护 `TripProfile` 槽位，必填齐全且用户确认后，由控制器调用 Tavily / wttr.in / 预算工具，再让 DeepSeek 生成结构化 `Itinerary`。工具与 LLM 均可注入，便于测试。

**Tech Stack:** Python 3.10、FastAPI、Uvicorn、openai SDK、tavily-python、httpx、Pydantic v2、pytest。

---

## 文件结构

```
travel-agent/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── errors.py
│   ├── schemas.py
│   ├── session.py
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── chat_agent.py
│   │   ├── profile.py
│   │   ├── prompts.py
│   │   └── tools/
│   │       ├── __init__.py
│   │       ├── attractions.py
│   │       ├── weather.py
│   │       └── budget.py
│   └── static/
│       ├── index.html
│       ├── app.js
│       └── style.css
├── tests/
│   ├── fixtures/weather_j1.json
│   ├── test_config.py
│   ├── test_schemas.py
│   ├── test_budget.py
│   ├── test_weather.py
│   ├── test_attractions.py
│   ├── test_profile.py
│   ├── test_chat_agent.py
│   └── test_api.py
├── .env / .env.example / .gitignore
├── requirements.txt
└── README.md
```

---

## Task 1：项目骨架与配置

**Files:** `requirements.txt`, `app/__init__.py`, `app/config.py`, `tests/test_config.py`

- [ ] 创建 venv：`python -m venv .venv`，安装依赖并冻结
- [ ] 写失败测试 `test_config.py`：缺少 `DEEPSEEK_API_KEY` 时 `Settings.load()` 抛 `ConfigError`；缺少 `TAVILY_API_KEY` 时标记 `degraded`
- [ ] 实现 `config.py`：`load_dotenv()`、`Settings` dataclass、`load()` 校验
- [ ] 运行 `pytest tests/test_config.py -v`，预期全部 PASS
- [ ] `git init` + 首次提交（`.env` 已被忽略）

**验收：** `python -c "from app.config import load; print(load())"` 不泄露密钥，能读出基础 URL。

---

## Task 2：Pydantic 数据模型

**Files:** `app/schemas.py`, `tests/test_schemas.py`

- [ ] 写失败测试：`CostRange` 拒绝 `min > max`；`Itinerary` 可往返序列化；`data_sources` 只接受 `tavily | wttr.in | estimate`
- [ ] 实现 `CostRange`、`Activity`、`WeatherInfo`、`DayPlan`、`BudgetBreakdown`、`Itinerary`
- [ ] 运行 `pytest tests/test_schemas.py -v`，预期 PASS

**关键契约：**

```python
class CostRange(BaseModel):
    min: float = Field(ge=0)
    max: float = Field(ge=0)
    @model_validator(mode="after")
    def check_order(self): ...
```

---

## Task 3：预算工具（纯函数）

**Files:** `app/agent/tools/budget.py`, `tests/test_budget.py`

- [ ] 写失败测试：
  - 经济/舒适/豪华三档，住宿单价递增
  - `travelers=2` 时餐饮与交通翻倍，住宿不翻倍
  - `ticket_total` 原样计入
  - `days <= 0` 抛 `ValueError`
- [ ] 实现常量表 `LODGING_RATE`、`FOOD_RATE`、`LOCAL_TRANSPORT_RATE` 与 `estimate_budget()`
- [ ] 运行 `pytest tests/test_budget.py -v`，预期 PASS

**验收：** 给定 `days=3, travelers=2, budget_level="舒适"`，各分项与总计均为 `min <= max` 的区间。

---

## Task 4：天气工具

**Files:** `app/agent/tools/weather.py`, `tests/test_weather.py`, `tests/fixtures/weather_j1.json`

- [ ] 准备 wttr.in `format=j1` 的固定 fixture（3 天）
- [ ] 写失败测试：
  - 正常解析出 3 条 `WeatherInfo`
  - 请求 5 天时，后 2 天 `unavailable=True`
  - 网络异常 → `ToolError(kind="weather_unavailable")`
- [ ] 实现 `async def get_weather(city, start_date, days, client=None)`
- [ ] 运行 `pytest tests/test_weather.py -v`，预期 PASS

**约束：** 只使用实际返回的 `weather` 数组，不补造数据。

---

## Task 5：景点搜索工具

**Files:** `app/agent/tools/attractions.py`, `tests/test_attractions.py`

- [ ] 写失败测试：
  - Tavily 标准响应 → `list[Attraction]`
  - 未配置 Key → `ToolError(kind="tavily_not_configured")`
  - 首次超时、重试成功 → 返回结果
  - 两次超时 → `ToolError(kind="tavily_unavailable")`
- [ ] 实现 `async def search_attractions(...)`，用 `asyncio.to_thread` 包装同步 Tavily SDK
- [ ] 运行 `pytest tests/test_attractions.py -v`，预期 PASS

---

## Task 6：TripProfile 槽位

**Files:** `app/agent/profile.py`, `tests/test_profile.py`

- [ ] 写失败测试：
  - 只填城市 → `missing_required() == ["days", "preferences"]`
  - 选填缺省 → `travelers=1`、`budget_level="舒适"`、`accommodation="酒店"`
  - `start_date="2026-11-20", end_date="2026-11-22"` → `days=3`
  - 合并更新不丢已有字段
- [ ] 实现 `TripProfile` 与 `merge()`、`missing_required()`、`is_complete()`
- [ ] 运行 `pytest tests/test_profile.py -v`，预期 PASS

---

## Task 7：ChatAgent 与提示词

**Files:** `app/agent/chat_agent.py`, `app/agent/prompts.py`, `tests/test_chat_agent.py`

- [ ] 写失败测试（注入 FakeLLM）：
  - 首轮用户只说"北京" → 回复只问一个问题，且包含"几天"
  - 槽位齐全但未确认 → 回复询问"开始规划吗"
  - 用户确认 → 调用 3 个工具并产出 `Itinerary`
  - 工具报错 → 回复明确说明数据不可用，不出现编造景点
  - 行程 JSON 非法 → 触发 1 次修复；仍非法 → 抛 `ItineraryGenerationError`
  - 单轮工具调用超过 6 次 → 中止并提示
- [ ] 实现 `ChatAgent.handle(message, session)`：
  1. LLM 抽取槽位 JSON（`extract_profile`）
  2. 必填缺失 → 模板化追问（保证一次一个）
  3. 齐全且 intent=plan → 调工具 → 生成行程 → 校验/修复
  4. 返回 `AgentTurn(reply, profile, itinerary | None, error | None)`
- [ ] 运行 `pytest tests/test_chat_agent.py -v`，预期 PASS

**提示词要求：** 抽取用严格 JSON；生成用严格 JSON schema；修复提示只允许修结构，不允许新增未提供的事实。

---

## Task 8：会话存储

**Files:** `app/session.py`, `tests/test_session.py`

- [ ] 写失败测试：创建/获取会话；历史超过 40 条时裁剪；同会话并发写被锁串行化
- [ ] 实现 `SessionStore`（dict + `asyncio.Lock` per session）
- [ ] 运行 `pytest tests/test_session.py -v`，预期 PASS

---

## Task 9：FastAPI 与 SSE

**Files:** `app/main.py`, `tests/test_api.py`

- [ ] 写失败测试：
  - `POST /api/session` 返回 `session_id`
  - `POST /api/chat` 返回 `text/event-stream`，事件顺序含 `profile`、`token`、`done`
  - 无 `session_id` 时自动建会话
  - `GET /api/health` 返回依赖状态
- [ ] 实现路由、SSE 生成器、静态文件挂载、依赖注入（LLM/工具可替换）
- [ ] 运行 `pytest tests/test_api.py -v`，预期 PASS

---

## Task 10：前端页面

**Files:** `app/static/index.html`, `app/static/app.js`, `app/static/style.css`

- [ ] 实现聊天布局、流式读取 SSE、槽位 chips、行程卡片、预算表、错误提示
- [ ] 手动验证：`uvicorn app.main:app --reload` 打开 `http://localhost:8000`
- [ ] 检查移动端 375px 宽度布局

**验收：** 输入"我想去北京玩三天，喜欢历史"能走完收集→确认→行程卡片。

---

## Task 11：端到端与文档

**Files:** `tests/test_e2e.py`, `README.md`

- [ ] 写集成测试：FakeLLM 走完 `COLLECTING → PLANNING → COMPLETED`
- [ ] 真实冒烟：DeepSeek + Tavily，记录一次实际输出
- [ ] 写 README：安装、.env、启动、API、已知限制
- [ ] 运行全量 `pytest -v`，预期 0 失败
- [ ] 提交

---

## 完成标准

- [ ] 全量测试通过，输出无 warning
- [ ] 真实 API 冒烟成功
- [ ] 槽位不全时绝不调用搜索工具
- [ ] 工具失败时回复中不出现编造数据
- [ ] 行程 JSON 100% 通过 Pydantic 校验
- [ ] README 可让新环境在 5 分钟内启动
