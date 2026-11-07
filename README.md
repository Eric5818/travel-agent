# 智能旅游推荐助手

本地运行的多轮聊天式旅游助手：通过对话收集目的地、天数和偏好，调用 Tavily 搜索景点、wttr.in 查询天气、Python 计算预算，再由 DeepSeek 生成带天气与预算的每日行程卡片。

## 功能

- 多轮对话收集槽位：目的地、天数、偏好（必填），出发日期、人数、预算档次、住宿类型（选填）
- 一次只追问一个必填槽位；选填项使用默认值并明确说明
- 槽位齐全且用户确认后才调用工具，避免无意义的搜索
- Tavily 景点搜索、真实门票票价、真实住宿参考价、wttr.in 天气、本地预算估算
- 票价按景点逐个并行查询，DeepSeek 批量抽取并做价格/来源证据校验
- 住宿返回 2–3 家参考酒店，展示每晚人民币区间、来源与查询日期
- 票价与住宿未知时明确标注，不以 0 或固定数字冒充
- SSE 流式返回：槽位更新、文本增量、行程 JSON、错误、结束事件
- 前端零构建：原生 HTML / CSS / JS，响应式布局
- 行程卡片按天展示天气、时间线活动、票价、住宿参考、预算分项与数据来源

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
- 结果：成功生成 3 天行程；9 个景点全部显示可追溯票价（故宫 40–60、景山 2–10、天坛 10–15、颐和园 20–30、圆明园 10、雍和宫 25、八达岭长城 35–40、恭王府 40、什刹海免费）；住宿参考 3 家酒店（和颐 493–563、首都宾馆 706–728 元/晚）；预算 **住宿 ¥986–¥1,456、门票 ¥182–¥230、总计 ¥1,708–¥2,766**；无未知项、无错误事件、无 JS 错误。

## 已知限制

| 限制 | 说明 |
|---|---|
| wttr.in 仅约 3 天预报 | 超出的日期标记 `unavailable`，不编造温度 |
| 会话存于内存 | 重启后清空，后续可迁移 SQLite |
| Tavily 免费额度 | 高频使用可能耗尽，暂未加缓存 |
| LLM JSON 不稳定 | 校验失败只修复 1 次，仍失败明确报错，不返回伪造行程 |
| 工具调用上限 | 单轮最多 6 次，超过即中止并提示 |
| 票价与酒店价格非实时 | 来自公开文章/OTA 摘要，可能与当日实际价格有差异；显示查询日期与来源，以官方/实际预订为准 |
| 住宿来源可能为历史文章 | 中文价格来源可能是往年文章，显示来源链接，后续可加发布时间过滤 |
| 住宿房间数 | 默认双人房，`ceil(人数/2)` 间；多人/特殊房型可能不准确 |
| 非人民币价格 | 票价与住宿只接受人民币证据，外币来源直接标未知 |
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
│   │   ├── chat_agent.py    # 槽位 → 确认 → 工具 → 生成 → 回填票价/住宿
│   │   ├── json_utils.py    # JSON 对象/数组解析
│   │   ├── profile.py       # TripProfile 槽位
│   │   ├── prompts.py       # 抽取 / 生成 / 修复 / 票价与住宿提示词
│   │   └── tools/           # 景点、票价、住宿、天气、预算、Tavily 助手
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
