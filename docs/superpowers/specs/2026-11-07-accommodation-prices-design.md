# 真实住宿参考价 设计文档

- **日期**：2026-11-07
- **状态**：已与用户逐段确认
- **关联项目**：智能旅游推荐助手
- **关联设计**：`2026-11-07-ticket-prices-design.md`

## 1. 背景与问题

当前住宿预算来自 `app/agent/tools/budget.py` 的固定单价表（舒适档 400–700 元/晚 × 晚数），界面会显示固定区间（如 3 天行程 ¥800–¥1,400）。行程中的「建议入住二环内酒店」是 LLM 文案，没有真实酒店名称、价格或来源。用户希望住宿也使用可追溯的真实参考价。

## 2. 目标与非目标

### 目标

- 为目的地查询 2–3 家符合住宿类型与预算档次的真实参考酒店
- 展示酒店名称、每晚价格区间、来源链接与查询日期
- 住宿预算改用真实参考区间 × 晚数 × 房间数
- 查不到时明确标注，不退回固定单价表
- `accommodation="不需要"` 时跳过查询并显示「不需要住宿」

### 非目标

- 不接入 OTA/酒店 API，不提供实时库存、房态或在线预订
- 不保证特定入住日期有房或价格不变
- 不做多酒店组合、位置距离排序或评分聚合
- 不做住宿长期缓存

## 3. 已确认决策

| 决策项 | 结论 |
|---|---|
| 数据程度 | 真实酒店参考价，含酒店名、区间、来源、查询日期 |
| 房间换算 | 默认双人房，房间数 = `ceil(travelers / 2)`，最少 1 间 |
| 预算口径 | 参考酒店最低–最高每晚区间 × 晚数 × 房间数 |
| 查不到时 | 标未知、预算 0、不退回固定数字 |
| 查询方式 | 一次 Tavily 城市级查询 + 一次 LLM 抽取 |

## 4. 架构

新增 `app/agent/tools/lodging.py`：

```python
async def get_accommodation_options(
    city: str,
    accommodation: str,
    budget_level: str,
    start_date: str | None,
    nights: int,
    travelers: int,
    llm,                      # async complete(messages) -> str
    client=None,              # Tavily 客户端，测试注入 fake
) -> LodgingResult:
    ...
```

内部步骤：

1. 若 `accommodation == "不需要"`：直接返回 `status="not_needed"`，不发起查询
2. **一次 Tavily 查询**
   - 查询词：`"{city} {accommodation} 每晚价格 元 携程 美团"`
   - 参数：`search_depth="advanced"`、`include_answer=True`、`max_results=5`、`country="china"`、`language="zh"`
   - 15 秒超时，失败重试 1 次
3. **一次 LLM 抽取**：输入除 Tavily `answer/results` 外，还包含 `city / accommodation / budget_level / month / nights / travelers`，让抽取器按档次筛选；最多保留 3 家证据完整的酒店
4. **证据校验**：酒店名、价格数字（必须紧邻人民币标记）、来源 URL 三项都必须能在本次结果中找到
5. 计算 `nightly_range`：有效酒店最低价的最小值 – 最高价的最大值
6. 有效酒店为 0 → `status="unknown"`

> **实现修订（2026-11-07）**：真实冒烟发现原始查询返回大量 USD/HKD/TWD/SGD/UZS 价格或动态订房页，无法满足人民币每晚价校验。改为 `country="china"` + `language="zh"` 的价格导向查询，并把用户档次与日期上下文传入抽取器后，成功返回 3 家可追溯的人民币参考酒店。

## 5. 抽取提示词规则

- 只输出 JSON 数组，每项包含 `name / min / max / note / source_url`
- 只接受标准房型的**每晚**价格；只给总价或套餐价时输出 unknown
- 排除税费、服务费、押金、餐饮套餐、钟点房
- 酒店名必须是来源中真实出现的名称
- `source_url` 必须属于输入来源
- 最多输出 3 家；没有可靠酒店时输出空数组
- JSON 非法时只修复 1 次；仍失败返回空数组

## 6. 证据校验

对每家酒店：

1. 酒店名出现在该次查询的任一结果标题或摘要中
2. `min <= max` 且均 >= 0
3. 价格数字必须紧邻人民币标记：`450 元`、`¥450`、`450 yuan`、`450–600 元` 等；仅在文本其他位置出现「元」不算
4. `source_url` 属于本次结果 URL 集合
5. 非人民币价格（US$ / HKD / TWD / SGD / UZS 等）→ 丢弃

任一条件不满足 → 丢弃该酒店。最终有效酒店为 0 → `unknown`。

## 7. 数据模型

```python
class HotelOption(BaseModel):
    name: str
    price_per_night: CostRange | None = None
    note: str = ""
    source_url: str | None = None

class LodgingResult(BaseModel):
    status: Literal["known", "unknown", "not_needed"]
    hotels: list[HotelOption] = Field(default_factory=list)
    nightly_range: CostRange | None = None
    note: str = ""

class Itinerary(BaseModel):
    # 现有字段不变
    accommodation_options: list[HotelOption] = Field(default_factory=list)
    accommodation_status: Literal["known", "unknown", "not_needed"] = "unknown"
    accommodation_note: str | None = None
```

- `known`：至少 1 家有效酒店，`nightly_range` 非空
- `unknown`：查询或抽取失败，或有效酒店为 0
- `not_needed`：用户选择「不需要」住宿

## 8. 数据流

`ChatAgent._plan` 最终顺序：

1. `search_attractions`
2. `get_ticket_prices`（无候选景点则跳过）
3. `get_accommodation_options`（`不需要` 则跳过）
4. `get_weather`
5. 生成行程（预算先以占位值满足 schema）
6. 回填门票
7. 用真实住宿区间与门票区间重算预算
8. 返回 `AgentTurn`

工具调用计数：景点搜索、票价查询、住宿查询、天气、预算各算 1 次，总上限 6。

## 9. 预算

```python
def estimate_budget(
    days, travelers, budget_level,
    ticket_total: float = 0,
    city_tier: int = 1,
    ticket_range: CostRange | None = None,
    lodging_range: CostRange | None = None,
) -> BudgetBreakdown:
```

- `lodging_range` 已包含晚数与房间数，直接作为住宿行
- 未传 `lodging_range` 时保持旧固定单价表行为
- 晚数：`days - 1`，单日行程按 1 晚
- 房间数：`max(1, ceil(travelers / 2))`
- 控制器计算：
  `住宿区间 = nightly_range × 晚数 × 房间数`
- 未知住宿：传入 `CostRange(0, 0)`，并设置 `accommodation_status="unknown"`
- `not_needed`：住宿 0，`accommodation_status="not_needed"`

## 10. 前端

- 行程卡片新增「住宿参考」区域，位于每日行程之后、预算表之前
- 每张酒店卡片：名称、`¥X – ¥Y / 晚`、备注、来源链接
- 区域底部统一提示：`参考价，查询于 YYYY-MM-DD；非实时库存，价格随日期浮动，以实际预订为准`
- 预算表住宿行使用真实区间
- `accommodation_status="unknown"`：住宿行显示 `未查到参考价，未计入`，不显示固定数字
- `accommodation_status="not_needed"`：显示 `不需要住宿`
- 每日行程里的住宿文案保留为区域建议，具体价格以「住宿参考」为准

## 11. 错误处理

| 场景 | 行为 |
|---|---|
| 酒店搜索超时/失败 | status unknown，行程继续 |
| 抽取 JSON 非法 | 修复 1 次；仍失败 → unknown |
| 有效酒店为 0 | unknown，预算住宿 0 并提示 |
| 单家酒店证据不足 | 丢弃该家，其他保留 |
| 超过 3 家 | 保留前 3 家 |
| 未指定出发日期 | 按当前月份查询并注明 |
| `accommodation="不需要"` | 跳过查询，状态 not_needed |
| 非人民币价格 | 丢弃；全部丢弃则 unknown |

## 12. 测试

- `tests/test_lodging.py`
  - known：2–3 家酒店、区间计算正确
  - not_needed：不发起 Tavily 调用
  - unknown：搜索失败、抽取失败、证据不足
  - JSON 非法 → 修复 1 次 → 仍失败 unknown
  - 超过 3 家截断
- `tests/test_budget.py`
  - `lodging_range` 生效；旧固定单价表行为不变
- `tests/test_chat_agent.py`
  - 住宿预算 = 区间 × 晚数 × `ceil(人数/2)`
  - 未知住宿不退回固定数字
  - 门票与住宿同时回填
- `tests/test_e2e.py`
  - SSE 全流程包含住宿参考与真实住宿预算
- 浏览器冒烟
  - 2–3 家酒店卡片、未知提示、375px 无回归
- 真实北京冒烟
  - 住宿预算不再固定为 ¥800–¥1,400，而是来自抽取的酒店区间

## 13. 验收标准

1. 真实北京舒适档冒烟显示 2–3 家可追溯酒店，住宿预算 > 0 且来自参考区间
2. 预算住宿行不再出现固定单价表的数值
3. 查不到酒店时显示「未查到参考价，未计入」，不使用固定数字
4. 原有测试与新增测试全绿，无 warning
5. 375px 布局无回归

## 14. 风险与限制

| 风险 | 影响 | 应对 |
|---|---|---|
| Tavily 价格非实时 | 与当日实际房价有差异 | 标注查询日期、非实时库存、以实际预订为准 |
| 中文价格来源可能为历史文章 | 房价可能过期 | 展示来源链接与查询日期；后续可加发布时间过滤 |
| 总价/套餐价被误读为每晚价 | 预算偏差 | 只接受明确每晚价；否则丢弃 |
| 酒店名证据匹配失败 | 有效酒店减少 | 保留 2–3 家目标，不足则全部标注 |
| 多人房型假设 | 房间数不准确 | 明确双人房假设；后续可让用户选房型 |
| Tavily 额度消耗 | 每次规划 +1 次查询 | 一次城市级查询；后续可加缓存 |

## 15. 性能影响

每次规划新增 1 次 Tavily 查询和 1 次 DeepSeek 抽取调用，预计增加 3–6 秒。
