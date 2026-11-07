# 真实门票票价 设计文档

- **日期**：2026-11-07
- **状态**：已与用户逐段确认
- **关联项目**：智能旅游推荐助手

## 1. 背景与问题

当前行程中的景点 `cost_estimate` 多为 `¥0–¥0`，预算门票行固定为 0：景点搜索只取了 Tavily 的 `results`，没有票价数据，也忽略了 Tavily 的 `answer`。真实检索验证表明，Tavily 的 `answer` 能返回可信票价（如故宫旺季 60／淡季 40、八达岭长城 40／35、颐和园 30／20、天坛 15／10），并带有官方或旅游站点来源。

## 2. 目标与非目标

### 目标

- 为行程中的每个景点展示真实票价区间或明确的「免费 / 未知」状态
- 票价必须可追溯到 Tavily 来源，并有证据校验
- 门票预算按行程实际使用的已知票价景点 × 出行人数计算
- 查不到票价时明确标注，不以 0 冒充，不阻断行程生成

### 非目标

- 不做实时票务库存、在线购票或支付
- 不接入携程/去哪儿等需要资质或额外 Key 的票务 API
- 不解析学生票、老年票、团队票、联票等特殊票种
- 不做票价长期持久化缓存（后续可加）

## 3. 已确认决策

| 决策项 | 结论 |
|---|---|
| 展示范围 | 行程中每个景点都展示票价状态 |
| 查询策略 | 逐景点并行 Tavily 查询 |
| 抽取方式 | 一次 DeepSeek 批量抽取 + 证据校验 |
| 季节票价 | 只展示价格区间，预算取区间 |
| 免费与未知 | 分开处理；未知不计入预算 |
| 人数 | 门票预算按出行人数累计 |
| 架构 | 独立票价解析器，与现有景点搜索工具并列 |

## 4. 架构

新增 `app/agent/tools/tickets.py`：

```python
async def get_ticket_prices(
    city: str,
    attractions: list[Attraction],
    llm,                      # 提供 async complete(messages) -> str
    client=None,              # Tavily 客户端，测试可注入 fake
    concurrency: int = 5,
) -> list[TicketInfo]:
    ...
```

内部步骤：

1. **并行查询**：对每个景点发一次 Tavily 搜索
   - 查询词：`"{city} {attraction.name} 门票价格 官方 预约"`
   - 参数：`search_depth="advanced"`、`include_answer=True`、`max_results=3`
   - 15 秒超时，失败重试 1 次；`asyncio.Semaphore(concurrency)` 限制并发
   - 同步 Tavily SDK 通过 `asyncio.to_thread` 调用
2. **汇总**：每个景点形成一个来源包（answer + results）
3. **批量抽取**：一次 LLM 调用，输入按序号编号的来源包，输出 JSON 数组
4. **证据校验**：逐条校验价格与来源
5. **按输入顺序**返回 `list[TicketInfo]`，失败项为 `unknown`

任一景点失败只影响该景点；全部失败也不抛出异常，行程继续生成。

## 5. 抽取提示词规则

- 只输出 JSON 数组，每项包含 `index / status / min / max / note / source_url`
- `status` 只能是 `known / free / unknown`
- 只取标准成人票；同一景点多档价格取最低–最高区间
- 排除学生票、老年票、儿童票、团队票、联票、讲解/导览附加费
- 只有来源明确写「免费」才输出 `free`
- 没有可靠数字时输出 `unknown`，禁止猜测
- `source_url` 必须是输入来源中出现的 URL
- JSON 非法时只修复 1 次；仍失败则全部标记 unknown

## 6. 证据校验

对每条 `known`：

1. `min <= max` 且均 >= 0
2. 价格数字（整数或小数，如 `60`、`60.0`、`60元`）必须出现在该景点的 answer 或任一 result content 中
3. `source_url` 必须属于该景点的本次结果 URL 集合

对 `free`：来源文本中必须出现「免费」。

任一条件不满足 → `unknown`，备注「票价证据不足」。

## 7. 数据模型

```python
TicketStatus = Literal["known", "free", "unknown"]

class TicketInfo(BaseModel):
    attraction: str
    status: TicketStatus
    price: CostRange | None = None
    note: str = ""
    source_url: str | None = None

class Activity(BaseModel):
    # 现有字段不变
    ticket_status: TicketStatus | None = None
    ticket_note: str | None = None
    ticket_source_url: str | None = None

class Itinerary(BaseModel):
    # 现有字段不变
    ticket_unknown_count: int = 0
```

- `ticket_status` 为 `None` 表示非景点活动（transfer/rest）
- 已知票价活动：`cost_estimate` 为票价区间，`ticket_status="known"`
- 免费：`cost_estimate=0–0`，`ticket_status="free"`
- 未知：`cost_estimate=None`，`ticket_status="unknown"`
- 已知/免费的 `ticket_note` 自动附加「查询于 YYYY-MM-DD，以景区官方为准」

## 8. 数据流

`ChatAgent._plan` 顺序（已按真实冒烟修正）：

1. `search_attractions`
2. `get_accommodation_options`（真实住宿参考价，详见 `2026-11-07-accommodation-prices-design.md`；`不需要` 则跳过）
3. `get_weather`
4. 生成行程（预算先用全 0 占位值，保证 schema 可校验）
5. **收集行程中的真实景点名**：遍历 `day_plans`，按名称去重
6. `get_ticket_prices`：用第 5 步的景点名逐个查询（无景点则跳过，不计工具调用）
7. **回填票价**：按景点名精确匹配 `TicketInfo`
   - 已知/免费：覆盖 `cost_estimate` 与票价字段
   - 未知或匹配不到：`ticket_status="unknown"`，`ticket_unknown_count += 1`
   - 非景点活动：不改动
8. **预算重算**：
   - 对行程中实际使用的景点去重
   - 单价区间求和 × `travelers` 得到门票总区间
   - 调用 `estimate_budget(..., ticket_range=总区间, lodging_range=住宿区间)`
   - 覆盖 `itinerary.budget`
9. 返回 `AgentTurn`

> **实现修订（2026-11-07）**：真实冒烟发现 `search_attractions` 返回的是 Tavily 文章标题（如「北京十大歷史人文景點…」），不是单个景点，导致提前用文章标题查票价全部 unknown。改为先生成行程，再用行程中 LLM 提炼出的真实景点名（如「故宫博物院」）查询票价，名称与回填完全对齐。验证结果：5 个真实景点名全部返回可追溯票价。

工具调用计数：景点搜索、住宿查询、天气、票价查询、预算各算 1 次；总上限仍为 6。

## 9. 预算接口

```python
def estimate_budget(
    days, travelers, budget_level,
    ticket_total: float = 0,
    city_tier: int = 1,
    ticket_range: CostRange | None = None,
    lodging_range: CostRange | None = None,
) -> BudgetBreakdown:
```

- `ticket_range` 优先；未传时保持旧的 `ticket_total` 标量行为
- `lodging_range` 为真实住宿总区间（晚数 × 房间数已在控制器中乘好）；未传时保持旧固定单价表行为
- 门票区间已经是「总价」（控制器已乘人数）
- 免费景点贡献 0；未知景点不贡献，只计入未知数量

## 10. 前端

- 景点活动时间线下显示：
  - 已知：`门票 ¥60 – ¥60`
  - 免费：`免费`
  - 未知：`票价未知，需官网确认`
  - 有票价来源时显示「票价来源」链接；原有「查看来源」保留
- 预算表门票行显示真实区间
- 若 `ticket_unknown_count > 0`，预算表下方提示：
  `另有 N 个景点未查到票价，未计入门票预算`
- 非景点活动不显示票价行

## 11. 错误处理

| 场景 | 行为 |
|---|---|
| 单个景点搜索超时/失败 | 该景点 unknown，其余继续 |
| 全部景点查询失败 | 全部 unknown，行程照常生成 |
| 抽取 JSON 非法 | 修复 1 次；仍失败全部 unknown |
| 证据校验失败 | 该项 unknown，不保留模型价格 |
| 无候选景点 | 跳过票价查询，不产生调用 |
| Tavily 未配置 | 景点搜索阶段已失败，不会进入票价查询 |

## 12. 测试

- `tests/test_tickets.py`
  - 并行查询按输入顺序返回
  - known / free / unknown 三种状态
  - 证据校验：摘要中不存在的价格、非本次来源 URL → unknown
  - 抽取 JSON 非法 → 修复 1 次；仍失败全部 unknown
  - 单个景点失败不影响其他景点
  - 空景点列表不发起查询
- `tests/test_budget.py`
  - `ticket_range` 生效
  - 旧 `ticket_total` 行为不变
- `tests/test_chat_agent.py`
  - 回填覆盖 LLM 写入的价格
  - 门票按人数累计
  - 未知计数正确
  - 票价查询失败不阻断行程
- `tests/test_e2e.py`
  - SSE 全流程包含活动票价状态与预算门票行
- 浏览器冒烟：known / free / unknown 三种展示与未知名额提示

## 13. 验收标准

1. 真实北京冒烟中，主要景点显示可追溯的票价区间，预算门票行大于 0
2. 所有价格数字都能在 Tavily 摘要中找到依据，来源链接属于本次结果
3. 查不到票价的景点显示未知且不计入预算，绝不显示 0 冒充
4. 原有 49 个测试继续通过，新增测试全绿，无 warning
5. 375px 布局无回归

## 14. 风险与限制

| 风险 | 影响 | 应对 |
|---|---|---|
| Tavily 摘要信息过时或不完整 | 票价不准确 | 显示查询日期与来源链接，注明以官方为准 |
| 景区搜索返回文章而非单个景点 | 票价查询名称错配 | 改为生成行程后使用活动中的真实景点名查询 |
| 数字证据校验存在误匹配 | 少量错误价格可能通过 | 价格数字必须紧邻「元/¥/RMB/CNY」；支持区间写法 |
| Tavily 额度消耗 | 每次规划最多 +8 次查询 | 并行执行；后续可加 24h 缓存 |
| 境外景点票价币种不同 | 预算失真 | 当前仅支持人民币；来源非人民币或无法判断时标 unknown |
| 景点名称与行程活动名称不完全一致 | 无法回填票价 | 精确匹配失败即标 unknown，不猜测 |

## 15. 性能影响

每次规划新增最多 8 次 Tavily 查询（并发上限 5）和 1 次 DeepSeek 抽取调用，预计增加 5–10 秒。
