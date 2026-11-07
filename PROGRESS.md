# 智能旅游推荐助手 — 项目进度

- **最后更新**：2026-11-07
- **项目路径**：`C:\Users\ASUS\Desktop\travel-agent`
- **远程仓库**：https://github.com/Eric5818/travel-agent （public）
- **当前分支**：`main`，与 `origin/main` 同步
- **当前阶段**：第一期功能全部完成，测试全绿，真实 API 冒烟通过
- **总体进度**：约 100%

---

## 一、项目目标

做一个本地运行的**多轮聊天式旅游推荐助手**：用户通过浏览器对话提供目的地、天数和偏好，助手调用真实数据源，生成包含每日行程、天气、住宿建议和预算估算的可视化行程卡片。

### 已确认的产品决策

| 决策项 | 结论 |
|---|---|
| 产品形态 | 多轮聊天式助手 |
| 聊天载体 | 本地网页（FastAPI + 原生 HTML/CSS/JS） |
| 数据源 | Tavily 搜索 + wttr.in 天气 |
| LLM | DeepSeek（OpenAI 兼容接口） |
| 第一期能力 | 景点推荐 + 每日行程 + 天气、住宿建议、预算估算 |
| 不做 | 餐饮推荐、在线预订、地图渲染、多用户、持久化、多 Agent 流水线 |
| 架构 | 单 Agent + TripProfile 槽位护栏（工具由控制器触发） |

---

## 二、已完成 ✅

### 1. 需求与设计（100%）

- 状态机：`COLLECTING → PLANNING → COMPLETED`
- 7 个槽位及必填/默认规则
- 3 个工具契约（景点 / 天气 / 预算）
- 行程数据结构、API、SSE 事件、错误处理、测试策略

设计文档：`docs/superpowers/specs/2026-11-07-travel-agent-design.md`

### 2. 实现计划（100%）

11 个任务，全部完成。计划文档：`docs/superpowers/plans/2026-11-07-travel-agent.md`

### 3. 实现任务（11 / 11）

| # | 任务 | 状态 | 结果 |
|---|---|---|---|
| 1 | 项目骨架与配置 | ✅ | venv、requirements、Settings/load()、密钥不泄露 |
| 2 | Pydantic 数据模型 | ✅ | CostRange/WeatherInfo/Activity/DayPlan/BudgetBreakdown/Itinerary |
| 3 | 预算工具 | ✅ | 三档单价 + 城市系数，纯函数 |
| 4 | 天气工具 | ✅ | wttr.in j1 解析，超出预报标记 unavailable |
| 5 | 景点搜索工具 | ✅ | Tavily 映射，超时重试 1 次，类型化错误 |
| 6 | TripProfile 槽位 | ✅ | 必填判定、默认值、日期换算天数 |
| 7 | ChatAgent 与提示词 | ✅ | 抽取 → 追问/确认 → 工具 → 生成/修复 |
| 8 | 会话存储 | ✅ | 内存 dict、40 条裁剪、每会话锁 |
| 9 | FastAPI + SSE | ✅ | session/health/chat，事件顺序正确 |
| 10 | 前端页面 | ✅ | 聊天、chips、行程卡片、预算表、375px 适配 |
| 11 | 端到端 + README | ✅ | 集成测试、真实冒烟、文档 |

### 4. 测试状态（89 passed，0 warning）

```text
tests/test_config.py        5 passed
tests/test_json_utils.py    6 passed
tests/test_schemas.py       6 passed
tests/test_budget.py        11 passed
tests/test_tavily_utils.py  7 passed
tests/test_weather.py       3 passed
tests/test_attractions.py   4 passed
tests/test_tickets.py       9 passed
tests/test_lodging.py       8 passed
tests/test_profile.py       6 passed
tests/test_chat_agent.py    11 passed
tests/test_session.py       5 passed
tests/test_api.py           7 passed
tests/test_e2e.py           1 passed
-----------------------------------
合计                        89 passed
```

运行命令：

```powershell
.\.venv\Scripts\python -m pytest -v
```

### 5. 真实冒烟（2026-11-07）

- DeepSeek `deepseek-chat` + Tavily + wttr.in
- 输入：`我想去北京玩三天，喜欢历史` → `好的，开始规划`
- 结果：3 天行程卡片正常渲染；槽位 chips 为「北京 / 3 天 / 历史人文 / 舒适 / 1 人 / 酒店」
- **真实票价**：9 个景点全部 known/free —— 故宫 40–60、景山 2–10、天坛 10–15、颐和园 20–30、圆明园 10、雍和宫 25、八达岭长城 35–40、恭王府 40、什刹海免费
- **真实住宿**：3 家参考酒店 —— 和颐中关村 493–532、和颐颐和园 526–563、首都宾馆 706–728 元/晚
- **预算**：住宿 ¥986–¥1,456、门票 ¥182–¥230、总计 ¥1,708–¥2,766
- 无未知项、无错误事件、无 JS 错误
- 前端另用真实浏览器验证了 375px 视口（`innerWidth=375`、`body.scrollWidth=375`，无横向溢出）

### 6. 环境与发布链路（100%）

- Python 3.10.11（用户级），项目内 `.venv`
- `requirements.txt` 已冻结全部依赖版本
- DeepSeek / Tavily Key 已验证并写入 `.env`（已忽略）
- Git 2.56.0、GitHub CLI 2.103.3 已安装并登录
- GitHub 定向代理：`http://127.0.0.1:12450`
- 远程仓库 public，`main` 分支已同步

### 7. 当前文件清单

```text
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
│   │   ├── json_utils.py
│   │   ├── profile.py
│   │   ├── prompts.py
│   │   └── tools/
│   │       ├── __init__.py
│   │       ├── attractions.py
│   │       ├── budget.py
│   │       ├── lodging.py
│   │       ├── tavily_utils.py
│   │       ├── tickets.py
│   │       └── weather.py
│   └── static/
│       ├── index.html
│       ├── app.js
│       └── style.css
├── tests/
│   ├── fixtures/weather_j1.json
│   ├── test_config.py
│   ├── test_json_utils.py
│   ├── test_schemas.py
│   ├── test_budget.py
│   ├── test_tavily_utils.py
│   ├── test_weather.py
│   ├── test_attractions.py
│   ├── test_tickets.py
│   ├── test_lodging.py
│   ├── test_profile.py
│   ├── test_chat_agent.py
│   ├── test_session.py
│   ├── test_api.py
│   └── test_e2e.py
├── docs/superpowers/specs/2026-11-07-travel-agent-design.md
├── docs/superpowers/specs/2026-11-07-ticket-prices-design.md
├── docs/superpowers/specs/2026-11-07-accommodation-prices-design.md
├── docs/superpowers/plans/2026-11-07-travel-agent.md
├── docs/superpowers/plans/2026-11-07-real-pricing.md
├── .env                  # 真实密钥，已忽略，绝不提交
├── .env.example
├── .gitignore
├── pytest.ini
├── requirements.txt
├── README.md
└── PROGRESS.md
```

### 8. 真实票价与住宿参考价（2026-11-07）

- [x] 票价工具：逐景点并行 Tavily 查询 + DeepSeek 批量抽取 + 证据校验
- [x] 票价状态：known / free / unknown；未知不显示 0
- [x] 住宿工具：中国/中文来源 + 每晚人民币价格，抽取 2–3 家酒店
- [x] 住宿参考：名称、每晚区间、来源链接、查询日期
- [x] 预算：门票 = 已用景点单价 × 人数；住宿 = 真实区间 × 晚数 × `ceil(人数/2)`
- [x] 未知住宿不退回固定单价表
- [x] 前端：活动票价、票价来源、住宿卡片、未知名额提示
- [x] 真实冒烟通过（见第 5 节）

> **执行中修正的两个根因**：
> 1. `search_attractions` 返回的是 Tavily 文章标题，不是单个景点。票价查询改为在行程生成后，用活动中的真实景点名（如「故宫博物院」）逐项查询，名称与回填完全对齐。
> 2. 住宿原查询返回大量外币/动态订房页。改为 `country="china"` + `language="zh"` 的价格导向查询，价格证据必须紧邻「元/¥/RMB/CNY」，并支持 `450–600 元` 区间写法。

---

## 三、实现中的决策与偏差

1. **`Itinerary` 字段重名**：设计文档同时写了 `days: int` 与 `days: list[DayPlan]`。实现采用 `days: int` + `day_plans: list[DayPlan]`，与 `TripProfile.days` 保持一致。
2. **天气不可用字段**：`WeatherInfo.temp_high_c / temp_low_c / chance_of_rain` 改为可选；超出预报范围时置 `None` 并标记 `unavailable=True`，避免用 0 冒充真实数据。
3. **预算注入**：LLM 只生成行程结构，`city / days / travelers / start_date / budget` 由控制器用可信值覆盖，防止模型改写预算。
4. **工具调用上限**：`ChatAgent.max_tool_calls` 默认 6，可注入更小值测试。
5. **住宿晚数**：预算中住宿按 `days - 1` 晚计（单日行程按 1 晚），符合常见出行习惯。
6. **天气描述语言**：wttr.in 原样返回英文描述，未做翻译。
7. **票价查询时机**：真实冒烟后从「生成前按候选查」改为「生成后按行程真实景点名查」，解决文章标题与景点名错配。
8. **住宿查询来源**：增加 `country="china"`、`language="zh"` 与「每晚价格 元 携程 美团」查询词；住宿抽取输入包含预算档次与日期上下文。
9. **人民币证据**：价格数字必须紧邻「元/¥/RMB/CNY」，支持区间写法；不再接受「文本任意位置出现元」的弱校验。

---

## 四、已知限制与风险

| 风险 | 影响 | 应对 |
|---|---|---|
| wttr.in 只有约 3 天预报 | 长行程天气不完整 | 超出天数标记不可用，提示出行前复查，不编造 |
| 会话存内存 | 重启丢失 | 第一期接受；后续可换 SQLite |
| Tavily 免费额度 | 高频使用可能耗尽 | 控制搜索次数，后续加缓存 |
| LLM 生成 JSON 不稳定 | 行程解析失败 | 校验 + 只修复一次；失败明确报错，不伪造兜底 |
| 票价/酒店价格非实时 | 与当日实际价格有差异 | 显示查询日期与来源，注明以官方/实际预订为准 |
| 住宿来源可能为历史文章 | 房价可能过期 | 展示来源链接；后续可加发布时间过滤 |
| 非人民币价格 | 外币来源无法直接使用 | 严格要求人民币证据，外币一律标未知 |
| 天气描述为英文 | 中文界面中出现英文 | 后续可加描述映射或本地化 |
| 代理客户端关闭 | git 无法访问 GitHub | 保持 `127.0.0.1:12450` 运行 |
| `.env` 含真实密钥 | 误提交会泄露 | 已 gitignore；每次提交前检查 |

---

## 五、下一步（可选增强）

1. 会话持久化（SQLite）与历史行程
2. 票价/住宿结果缓存（24h）与 Tavily 额度保护
3. 住宿来源发布时间过滤、房型选择与实时库存 API
4. 天气描述中文化、门票优惠票种（学生/老人）
5. 餐饮推荐、真实 POI / 地图
6. 导出 PDF / 分享链接、多城市联程

---

## 六、恢复工作的方法

新会话中按以下顺序阅读：

1. 本文件 `PROGRESS.md`
2. `README.md`（安装、启动、API）
3. 设计文档与实现计划（`docs/superpowers/`）

### 环境自检

```powershell
.\.venv\Scripts\python --version
.\.venv\Scripts\python -c "import fastapi, openai, tavily, pydantic; print('deps ok')"
git --version
gh auth status
```

### 仓库自检

```powershell
git -C "C:\Users\ASUS\Desktop\travel-agent" status -sb
git -C "C:\Users\ASUS\Desktop\travel-agent" log --oneline -5
```

### 启动与验证

```powershell
.\.venv\Scripts\python -m uvicorn app.main:app --reload
.\.venv\Scripts\python -m pytest -v
```

### 提交与推送

```powershell
$proj = "C:\Users\ASUS\Desktop\travel-agent"
git -C $proj add -A
git -C $proj commit -m "feat: ..."
git -C $proj push origin main
```

> 推送前务必确认 `git status` 中没有 `.env`。
