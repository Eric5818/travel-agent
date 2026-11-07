# 智能旅游推荐助手 — 设计文档

- **日期**：2026-11-07
- **状态**：已与用户确认
- **项目路径**：`C:\Users\ASUS\Desktop\travel-agent`

## 1. 目标

做一个本地运行的**多轮聊天式旅游推荐助手**。用户通过自然语言对话提供目的地、天数和偏好，助手在信息齐全后调用真实数据源，生成包含每日行程、天气、住宿建议和预算估算的可视化行程卡片。

### 非目标（V1 不做）

- 不做餐饮推荐（预算中保留餐饮费用）
- 不做在线预订、支付、真实地图渲染
- 不做多用户账号体系
- 不做行程持久化（重启清空）
- 不做多 Agent 流水线

## 2. 用户流程

1. 打开浏览器，进入聊天页。
2. 助手问候并询问目的地；用户回答后，一次追问一个必填项（天数、偏好）。
3. 选填项（出发日期、人数、预算档次、住宿类型）使用默认值，并在回复中说明默认假设。
4. 必填项齐全后，助手确认理解并询问是否开始规划。
5. 用户确认后，助手调用 Tavily 搜索景点、wttr.in 查询天气、Python 计算预算，生成结构化疗程。
6. 前端渲染行程卡片；用户可以继续对话做增量修改（如"第二天改成室内"）。

## 3. 总体架构

```
浏览器 (localhost:8000)
   │  POST /api/chat  (SSE 流式)
   ▼
FastAPI 后端
   ├─ ChatAgent ── DeepSeek (OpenAI 兼容 API)
   ├─ TripProfile 槽位校验
   ├─ 工具: search_attractions / get_weather / estimate_budget
   └─ 内存会话存储 (session_id → 历史 + profile)
```

- 前端为**零构建**的原生 HTML/CSS/JS，由 FastAPI 托管。
- 后端使用 `asyncio`，LLM 与工具调用均异步执行。
- 每个会话持有独立锁，防止并发写坏历史。

## 4. 技术栈

| 层 | 选择 | 备注 |
|---|---|---|
| Web 框架 | FastAPI + Uvicorn | `/api/chat` 使用 SSE |
| 前端 | 原生 HTML / CSS / JS | 无构建步骤 |
| LLM | DeepSeek `deepseek-chat` | 已验证：`https://api.deepseek.com/v1` |
| 景点搜索 | Tavily Python SDK | 需要 `TAVILY_API_KEY` |
| 天气 | wttr.in `?format=j1` | 免费、无需 Key |
| 数据校验 | Pydantic v2 | 工具结果与行程 schema |
| 测试 | pytest + pytest-asyncio + httpx | 外部 API 全部 mock |
| 配置 | python-dotenv | `.env` 文件 |
| 运行环境 | 项目内 venv | 不污染全局 Python |

## 5. 槽位定义（TripProfile）

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `destination` | `str` | ✅ | — | 城市或地区 |
| `days` | `int` | ✅ | — | 天数；日期区间自动换算 |
| `preferences` | `list[str]` | ✅ | — | 自然风光/历史人文/亲子/美食/购物/休闲 |
| `start_date` | `date \| None` | ❌ | `None` | 影响天气可用性 |
| `travelers` | `int` | ❌ | `1` | 用于预算 |
| `budget_level` | `经济 \| 舒适 \| 豪华` | ❌ | `舒适` | 预算档次 |
| `accommodation` | `酒店 \| 民宿 \| 青旅 \| 不需要` | ❌ | `酒店` | 住宿建议 |

**收集规则**：

- 一次只追问一个必填槽位。
- 选填槽位使用默认值，且必须在助手回复中显式说明假设。
- 用户修改已填槽位时，覆盖旧值并重新校验。

## 6. 对话状态机

```
COLLECTING ──必填齐 + 用户确认规划──▶ PLANNING ──行程校验通过──▶ COMPLETED
     ▲                                                              │
     └──────────────── 用户改变需求（如换城市）────────────────────┘
```

### 硬规则

1. 必填槽位未齐时，禁止进入 PLANNING，禁止调用搜索工具。
2. 工具未返回的数据不得出现在行程中；无法获取时明确说明。
3. 单轮对话最多 6 次工具调用，超过则停止并告知用户。

## 7. 工具契约

### 7.1 `search_attractions`

```python
search_attractions(city: str, keywords: list[str], limit: int = 8) -> list[Attraction]
```

- Tavily 查询：`"{city} {keywords} 景点 攻略 推荐"`，`search_depth="advanced"`，`include_answer=True`
- 超时 15 秒；失败重试 1 次
- 返回 `Attraction`：`name, category, description, address?, source_url`
- 未配置 Key 或调用失败时返回类型化错误，由 Agent 如实转述

### 7.2 `get_weather`

```python
get_weather(city: str, start_date: str, days: int) -> WeatherReport
```

- 数据源：`https://wttr.in/{city}?format=j1`
- 仅返回实际可用的预报日期（通常 3 天）
- 超出预报范围的日期标记 `unavailable=True`，不得编造
- 返回：`date, weather_desc, temp_high_c, temp_low_c, chance_of_rain, suggestion, unavailable`

### 7.3 `estimate_budget`

```python
estimate_budget(days, travelers, budget_level, ticket_total=0, city_tier=1) -> BudgetBreakdown
```

- 纯 Python 查表计算，不经过 LLM
- 覆盖住宿、餐饮、市内交通、门票
- 各分项与总计均返回 `min` / `max` 区间
- 具体单价表在实现计划中定义，并集中为代码常量，便于调整

## 8. 数据模型（Pydantic）

```python
Itinerary:
  city: str
  start_date: date | None
  days: int
  travelers: int
  summary: str
  days: list[DayPlan]
  budget: BudgetBreakdown
  tips: list[str]
  data_sources: list[Literal["tavily", "wttr.in", "estimate"]]

DayPlan:
  date: str
  day_index: int
  theme: str
  weather: WeatherInfo | None
  activities: list[Activity]
  accommodation: str | None
  daily_cost: CostRange

Activity:
  time: str
  name: str
  type: Literal["attraction", "transfer", "rest"]
  duration_min: int
  description: str
  location_hint: str | None
  cost_estimate: CostRange | None
  source_url: str | None

CostRange:
  min: float
  max: float
```

## 9. API 设计

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/` | 返回聊天页面 |
| `POST` | `/api/chat` | 请求 `{session_id, message}`，SSE 返回文本增量、状态、行程 JSON |
| `GET` | `/api/health` | 返回各依赖配置状态（llm/tavily/weather） |
| `POST` | `/api/session` | 创建新会话，返回 `session_id` |

SSE 事件类型：

- `token`：文本增量
- `profile`：槽位更新
- `itinerary`：完整行程 JSON
- `error`：可读错误信息
- `done`：本轮结束

## 10. 错误处理

| 场景 | 行为 |
|---|---|
| 缺少 `DEEPSEEK_API_KEY` | 启动日志报错，服务仍可启动，`/api/health` 标记 degraded |
| 缺少 `TAVILY_API_KEY` | 景点工具返回明确错误，Agent 告知用户并建议配置 |
| LLM 超时/报错 | 发送 SSE `error` 事件，保留会话状态，提示重试 |
| 工具超时 | 重试 1 次；仍失败返回类型化错误，Agent 如实说明 |
| 行程 JSON 不合法 | 使用修复提示重试 1 次；仍失败返回 `error` + 原始内容，不生成伪造兜底行程 |
| 会话不存在 | 自动创建新会话 |
| 同一会话并发请求 | 每会话 `asyncio.Lock` 串行处理 |

## 11. 前端行为

- 聊天气泡 + 流式文字输出
- 顶部槽位 chips：目的地 · 天数 · 偏好 · 预算档次，随对话实时更新
- 行程卡片：
  - 按天分栏
  - 每天显示天气、时间线活动、住宿
  - 预算表分项与总计
  - 底部显示数据来源
- 输入框支持增量修改指令
- 移动端可用的响应式布局

## 12. 测试策略

| 层级 | 内容 |
|---|---|
| 单元 | 槽位缺失判定、日期→天数换算、预算表计算、wttr.in JSON 解析（含缺失天数）、Tavily 响应映射、超时错误映射 |
| 契约 | 行程 JSON 校验、非法 JSON 触发一次修复、修复失败不伪造兜底 |
| 集成 | FakeLLM 脚本化输出，验证 `COLLECTING → PLANNING → COMPLETED` 的 SSE 全流程 |
| 手工 | 真实 DeepSeek + Tavily 冒烟测试一次 |

开发遵循 TDD：每个模块先写失败测试，再写最小实现。

## 13. 项目结构

```
travel-agent/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── session.py
│   ├── schemas.py
│   ├── agent/
│   │   ├── chat_agent.py
│   │   ├── prompts.py
│   │   └── tools/
│   │       ├── attractions.py
│   │       ├── weather.py
│   │       └── budget.py
│   └── static/
│       ├── index.html
│       ├── app.js
│       └── style.css
├── tests/
├── .env.example
├── requirements.txt
└── README.md
```

## 14. 依赖

```
fastapi
uvicorn[standard]
openai
python-dotenv
requests
tavily-python
pydantic
pytest
pytest-asyncio
httpx
```

## 15. 假设与待办

- 用户需要自行申请 Tavily API Key（免费额度）；未提供前只能用假数据跑测试。
- wttr.in 仅提供约 3 天预报；更长行程的天气按"部分可用 + 出行前复查"处理。
- 会话存储在内存，重启清空；后续可迁移 SQLite。
- 项目尚未初始化 git；实现阶段第一步会 `git init` 并提交本设计文档。

## 16. 后续可扩展

- 餐饮推荐与真实餐厅 POI
- 高德地图 MCP 接入（POI / 路线 / 地图展示）
- SQLite 持久化与历史行程
- 导出 PDF / 分享链接
- 多城市联程与交通衔接
