# 智能旅游推荐助手 — 项目进度

- **最后更新**：2026-11-07
- **项目路径**：`C:\Users\ASUS\Desktop\travel-agent`
- **当前阶段**：设计与计划完成，尚未开始编码
- **总体进度**：约 25%（设计 100%，实现 0%，发布 0%）

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

### 1. 需求与设计

- [x] 明确产品形态、数据源、LLM、能力范围
- [x] 确定架构：`COLLECTING → PLANNING → COMPLETED` 状态机
- [x] 定义 7 个槽位及必填/默认规则
- [x] 定义 3 个工具契约（景点 / 天气 / 预算）
- [x] 定义行程数据结构与 API
- [x] 设计错误处理与测试策略

设计文档：

```
docs/superpowers/specs/2026-11-07-travel-agent-design.md
```

### 2. 实现计划

- [x] 拆分为 11 个任务，含文件路径、测试用例、验收标准

计划文档：

```
docs/superpowers/plans/2026-11-07-travel-agent.md
```

### 3. 环境与凭证

- [x] Python 3.10.11 已安装（用户级）
  - 路径：`C:\Users\ASUS\AppData\Local\Programs\Python\Python310`
- [x] 全局已安装 `openai 3.46.0`、`python-dotenv 1.2.4`
- [x] DeepSeek Key 已验证：`https://api.deepseek.com/v1` 可正常调用
- [x] Tavily Key 已验证：搜索「北京 景点」返回 2 条结果
- [x] `.env` 已写入 DeepSeek / Tavily 配置（本地，不提交）
- [x] `.env.example` 已创建（只有占位符）
- [x] `.gitignore` 已创建，已排除 `.env`、venv、缓存等

当前项目文件：

```
travel-agent/
├── .env                  # 真实密钥，已被忽略
├── .env.example          # 占位符模板
├── .gitignore
├── PROGRESS.md           # 本文件
└── docs/
    ├── superpowers/specs/2026-11-07-travel-agent-design.md
    └── superpowers/plans/2026-11-07-travel-agent.md
```

### 4. Git 与远程仓库

- [x] 安装 Git 2.56.0
- [x] 配置 git 身份：`Eric5818` / `3040222984@qq.com`
- [x] `git init -b main` 并完成首次提交 `f1aa051`
- [x] 通过 GitHub Desktop 发布公开仓库
- [x] 配置 `http.https://github.com.proxy = http://127.0.0.1:12450`
- [x] 验证远程 `main` 与本地一致、仓库为 public
- [x] 确认 `.env` 未被跟踪、已跟踪文件中无密钥

远程地址：

```
https://github.com/Eric5818/travel-agent
```

---

## 三、未完成 ❌

### 实现任务（0 / 11）

| # | 任务 | 状态 | 关键验收 |
|---|---|---|---|
| 1 | 项目骨架与配置 | ❌ 未开始 | 缺 Key 明确报错，不泄露密钥 |
| 2 | Pydantic 数据模型 | ❌ 未开始 | 行程可往返序列化 |
| 3 | 预算工具 | ❌ 未开始 | 纯函数、区间正确、人数逻辑对 |
| 4 | 天气工具 | ❌ 未开始 | 超预报天数标记不可用，不编造 |
| 5 | 景点搜索工具 | ❌ 未开始 | Tavily 映射、超时重试、未配置报错 |
| 6 | TripProfile 槽位 | ❌ 未开始 | 缺什么问什么，默认值正确 |
| 7 | ChatAgent + 提示词 | ❌ 未开始 | 槽位不全不调工具；JSON 非法只修复一次 |
| 8 | 会话存储 | ❌ 未开始 | 历史裁剪、并发锁 |
| 9 | FastAPI + SSE | ❌ 未开始 | 事件顺序正确、依赖可注入 |
| 10 | 前端页面 | ❌ 未开始 | 聊天 + 槽位 chips + 行程卡片 |
| 11 | 端到端 + README | ❌ 未开始 | 全量测试通过 + 真实冒烟 |

### 环境准备（尚未做）

- [ ] 创建项目 venv（`.venv`）
- [ ] 编写 `requirements.txt`
- [ ] 安装项目依赖（fastapi、uvicorn、tavily-python、httpx、pytest 等）

### 发布到 Git（已完成）

- [x] 选择发布方式：Git + GitHub Desktop
- [x] 安装 Git 并配置身份
- [x] 初始化仓库并首次提交
- [x] 创建公开远程仓库并推送
- [x] 确认 `.env` 未被提交、仓库历史中无密钥

---

## 四、当前阻塞与待决事项

**当前无阻塞。**

补充说明：

1. `gh` CLI 已安装但未登录。GitHub Desktop 已完成认证与发布，因此 gh 不是必需。若以后想用 `gh` 管理 Issue/PR，需在带代理的终端里重新 `gh auth login --web`。
2. 直连 `github.com:443` 不稳定，已为 git 配置定向代理 `http://127.0.0.1:12450`。**代理客户端必须保持运行**，否则 fetch/push 会超时。
3. 仓库当前为 **public**，代码与设计文档对所有人可见。

---

## 五、已知限制与风险

| 风险 | 影响 | 应对 |
|---|---|---|
| wttr.in 只有约 3 天预报 | 长行程天气不完整 | 超出天数标记不可用，提示出行前复查，不编造 |
| 会话存内存 | 重启丢失 | 第一期接受；后续可换 SQLite |
| Tavily 免费额度 | 高频使用可能耗尽 | 控制搜索次数，加缓存可后续做 |
| LLM 生成 JSON 不稳定 | 行程解析失败 | 校验 + 只修复一次；失败明确报错，不伪造兜底 |
| 模型自由调用工具不可控 | 可能提前搜索或死循环 | 工具由控制器按槽位触发，硬限制 6 次 |
| `.env` 含真实密钥 | 误提交会泄露 | 已 gitignore；推送前再次 `git check-ignore` 验证 |

---

## 六、下一步（按顺序）

1. 执行 Task 1：创建 venv、`requirements.txt`、`config.py` 及其测试
2. 依次完成 Task 2-11（严格 TDD）
3. 真实 API 冒烟测试
4. 写 README，提交并推送
5. 本地与远程全量测试通过后，更新本文件的进度

---

## 七、恢复工作的方法

新会话中按以下顺序阅读即可继续：

1. 本文件 `PROGRESS.md`
2. 设计文档 `docs/superpowers/specs/2026-11-07-travel-agent-design.md`
3. 实现计划 `docs/superpowers/plans/2026-11-07-travel-agent.md`
4. 从计划的 **Task 1** 开始执行

验证环境是否仍可用：

```powershell
python --version
python -c "import openai, dotenv; print('deps ok')"
```

验证密钥是否仍有效（不打印密钥）：

```powershell
# Tavily
python -c "import os; from dotenv import load_dotenv; load_dotenv(); import urllib.request, json; k=os.environ['TAVILY_API_KEY']; req=urllib.request.Request('https://api.tavily.com/search', data=json.dumps({'api_key':k,'query':'test','max_results':1}).encode(), headers={'Content-Type':'application/json'}); print('tavily', urllib.request.urlopen(req, timeout=30).status)"
```

```powershell
# DeepSeek
python -c "import os; from dotenv import load_dotenv; load_dotenv(); from openai import OpenAI; c=OpenAI(api_key=os.environ['DEEPSEEK_API_KEY'], base_url=os.environ['DEEPSEEK_BASE_URL']); r=c.chat.completions.create(model=os.environ['DEEPSEEK_MODEL'], messages=[{'role':'user','content':'hi'}], max_tokens=5); print('deepseek ok')"
```
