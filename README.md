# 智能旅游推荐助手

本地运行的多轮聊天式旅游助手：通过对话收集目的地、天数和偏好，调用 Tavily 搜索景点、wttr.in 查询天气、Python 计算预算，再由 DeepSeek 生成带天气与预算的每日行程卡片。

## 功能

- 多轮对话收集槽位：目的地、天数、偏好（必填），出发日期、人数、预算档次、住宿类型（选填）
- 一次只追问一个必填槽位；选填项使用默认值并明确说明
- 槽位齐全且用户确认后才调用工具，避免无意义的搜索
- Tavily 景点搜索、wttr.in 天气、本地预算估算
- SSE 流式返回：槽位更新、文本增量、行程 JSON、错误、结束事件
- 前端零构建：原生 HTML / CSS / JS，响应式布局
- 行程卡片按天展示天气、时间线活动、住宿、预算分项与数据来源

## 技术栈

| 层 | 选择 |
|---|---|
| Web 框架 | FastAPI + Uvicorn |
| 前端 | 原生 HTML / CSS / JS |
| LLM | DeepSeek（OpenAI 兼容接口） |
| 景点搜索 | Tavily Python SDK |
| 天气 | wttr.in `?format=j1` |
| 数据校验 | Pydantic v2 |
| 测试 | pytest + pytest-asyncio + httpx |

## 快速开始

要求 Python 3.10+。

```powershell
git clone https://github.com/Eric5818/travel-agent.git
cd travel-agent

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Linux / macOS：

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### 配置 `.env`

```powershell
Copy-Item .env.example .env
```

编辑 `.env`：

| 变量 | 必填 | 说明 |
|---|---|---|
| `DEEPSEEK_API_KEY` | ✅ | DeepSeek API Key |
| `DEEPSEEK_BASE_URL` | 否 | 默认 `https://api.deepseek.com/v1` |
| `DEEPSEEK_MODEL` | 否 | 默认 `deepseek-chat` |
| `TAVILY_API_KEY` | 建议 | 缺失时景点搜索不可用，接口标记 degraded |
| `WEATHER_BASE_URL` | 否 | 默认 `https://wttr.in` |

> `.env` 已被 `.gitignore` 忽略，**不要提交**。

### 启动

```powershell
python -m uvicorn app.main:app --reload
```

打开 <http://localhost:8000>。

可以输入：

```text
我想去北京玩三天，喜欢历史
```

助手会确认信息并询问是否开始规划；回复「好的，开始规划」后生成行程卡片。

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/` | 聊天页面 |
| `GET` | `/api/health` | 依赖状态：`llm` / `tavily` / `weather` / `degraded` |
| `POST` | `/api/session` | 创建会话，返回 `session_id` |
| `POST` | `/api/chat` | 请求 `{message, session_id?}`，SSE 返回 |

### SSE 事件

| 事件 | 数据 | 说明 |
|---|---|---|
| `session` | `{session_id}` | 当前会话 id；未传时自动创建 |
| `profile` | 槽位 JSON | 每轮更新后的 TripProfile |
| `itinerary` | 行程 JSON | 仅在成功生成时发送 |
| `error` | `{kind, message}` | 可读错误信息 |
| `token` | `{text}` | 回复文本增量 |
| `done` | `{}` | 本轮结束 |

## 测试

```powershell
python -m pytest -v
```

覆盖配置、数据模型、预算、天气、景点、槽位、ChatAgent、会话、API 与端到端流程。外部 API 全部使用 fake / fixture，测试不产生真实网络请求。

## 真实冒烟记录

- 日期：2026-11-07
- 模型：DeepSeek `deepseek-chat`；数据源：Tavily + wttr.in
- 输入：`我想去北京玩三天，喜欢历史` → `好的，开始规划`
- 结果：成功生成 3 天行程，槽位 chips 更新为「北京 / 3 天 / 历史人文 / 舒适 / 1 人 / 酒店」；每日含天气、活动与住宿；预算约 **¥1,340 – ¥2,480**；数据来源显示 Tavily / wttr.in / 本地估算；无错误事件。

## 已知限制

| 限制 | 说明 |
|---|---|
| wttr.in 仅约 3 天预报 | 超出的日期标记 `unavailable`，不编造温度 |
| 会话存于内存 | 重启后清空，后续可迁移 SQLite |
| Tavily 免费额度 | 高频使用可能耗尽，暂未加缓存 |
| LLM JSON 不稳定 | 校验失败只修复 1 次，仍失败明确报错，不返回伪造行程 |
| 工具调用上限 | 单轮最多 6 次，超过即中止并提示 |
| 门票费用 | 景点搜索未返回票价时门票按 0 计，预算中不估算不存在的票价 |
| 天气描述语言 | wttr.in 原样返回英文描述（如 Overcast） |
| 不做 | 餐饮推荐、在线预订、地图渲染、多用户、持久化、多 Agent |

## 项目结构

```text
travel-agent/
├── app/
│   ├── main.py              # FastAPI、SSE、静态资源
│   ├── config.py            # .env 加载与配置校验
│   ├── errors.py            # ToolError / ItineraryGenerationError
│   ├── schemas.py           # Pydantic 数据模型
│   ├── session.py           # 会话存储与每会话锁
│   ├── agent/
│   │   ├── chat_agent.py    # 槽位 → 确认 → 工具 → 生成流程
│   │   ├── profile.py       # TripProfile 槽位
│   │   ├── prompts.py       # 抽取 / 生成 / 修复提示词
│   │   └── tools/           # 景点、天气、预算
│   └── static/              # 前端页面
├── tests/                   # pytest 测试与 fixture
├── docs/superpowers/        # 设计与实现计划
├── requirements.txt
└── PROGRESS.md              # 进度与恢复入口
```

## 调整预算

预算单价集中在 `app/agent/tools/budget.py` 的 `LODGING_RATE`、`FOOD_RATE`、`LOCAL_TRANSPORT_RATE` 与 `CITY_TIER_FACTOR`，按需修改即可，不影响其他模块。

## 安全

- `.env` 含真实密钥，已被 `.gitignore` 排除
- 提交前建议检查：`git status --short` 与 `git ls-files | grep .env`
- GitHub Token 与代理属于本机环境配置，不应写入仓库
