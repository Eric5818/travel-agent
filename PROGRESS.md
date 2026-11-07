# 智能旅游推荐助手 — 项目进度

- **最后更新**：2026-11-07
- **项目路径**：`C:\Users\ASUS\Desktop\travel-agent`
- **远程仓库**：https://github.com/Eric5818/travel-agent （public）
- **当前分支**：`main`，与 `origin/main` 同步
- **当前阶段**：设计与计划完成，环境与发布链路就绪，尚未开始编码
- **总体进度**：约 30%

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

- [x] 明确产品形态、数据源、LLM、能力范围
- [x] 确定状态机：`COLLECTING → PLANNING → COMPLETED`
- [x] 定义 7 个槽位及必填/默认规则
- [x] 定义 3 个工具契约（景点 / 天气 / 预算）
- [x] 定义行程数据结构、API、SSE 事件
- [x] 定义错误处理、测试策略、项目结构

设计文档：

```
docs/superpowers/specs/2026-11-07-travel-agent-design.md
```

### 2. 实现计划（100%）

- [x] 拆分为 11 个任务，含文件路径、测试用例、验收标准

计划文档：

```
docs/superpowers/plans/2026-11-07-travel-agent.md
```

### 3. 本地运行环境（100%）

- [x] Python 3.10.11（用户级安装）
  - `C:\Users\ASUS\AppData\Local\Programs\Python\Python310`
- [x] 全局已安装 `openai 3.46.0`、`python-dotenv 1.2.4`
- [x] pip 26.3
- [x] `python` / `pip` 已加入用户 PATH

### 4. API 凭证（100%）

- [x] DeepSeek Key 验证通过：`https://api.deepseek.com/v1`
- [x] Tavily Key 验证通过：搜索「北京 景点」返回结果
- [x] `.env` 已创建，包含 DeepSeek / Tavily 配置
- [x] `.env.example` 已创建，只有占位符
- [x] `.gitignore` 已排除 `.env`
- [x] 已确认 `.env` 未被 git 跟踪，仓库历史中无密钥

### 5. Git 与发布链路（100%）

- [x] Git 2.56.0 已安装（`C:\Program Files\Git`）
- [x] git 身份：`Eric5818` / `3040222984@qq.com`
- [x] GitHub CLI 2.103.3 已安装
- [x] gh 已登录，Token 保存于系统 keyring
- [x] Token 为 fine-grained，已确认权限：`Contents: Read and write`
- [x] `gh auth setup-git` 已执行，CLI 可直接推送
- [x] 已配置 GitHub 定向代理：`http://127.0.0.1:12450`
- [x] 远程仓库为 **public**，默认分支 `main`
- [x] 本地与远程已同步，工作区干净

### 6. Git 提交历史

```
baa8af0  docs: 更新进度并记录远程仓库信息
f1aa051  docs: 初始化旅游助手的设计文档与实现计划
```

### 7. 当前文件清单

```
travel-agent/
├── .env                  # 真实密钥，已被忽略，绝不提交
├── .env.example          # 占位符模板
├── .gitignore
├── PROGRESS.md           # 本文件
└── docs/
    └── superpowers/
        ├── specs/2026-11-07-travel-agent-design.md    # 设计（9 KB）
        └── plans/2026-11-07-travel-agent.md           # 计划（8 KB）
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

- [ ] 创建项目 venv：`python -m venv .venv`
- [ ] 编写 `requirements.txt`
- [ ] 安装项目依赖：
  - `fastapi`
  - `uvicorn[standard]`
  - `openai`
  - `python-dotenv`
  - `requests`
  - `tavily-python`
  - `pydantic`
  - `pytest`
  - `pytest-asyncio`
  - `httpx`

---

## 四、当前阻塞与待决事项

**当前无阻塞。** 环境、凭证、Git、代理、推送链路均已验证。

需要长期注意的三点：

1. **代理必须运行**：直连 `github.com:443` 不稳定，git 已配置定向代理 `http://127.0.0.1:12450`。代理客户端关闭时，fetch/push 会超时。
2. **Token 有效期**：当前 fine-grained Token 有到期时间。到期或撤销后，需重新生成并执行：
   ```powershell
   gh auth login --with-token
   gh auth setup-git
   ```
   注意：PowerShell 管道可能给 Token 加换行，建议用 cmd 重定向：
   ```cmd
   gh auth login --with-token < token.txt
   ```
3. **仓库是公开的**：代码与设计文档对所有人可见。`.env` 已忽略，但提交前仍应检查。

---

## 五、已知限制与风险

| 风险 | 影响 | 应对 |
|---|---|---|
| wttr.in 只有约 3 天预报 | 长行程天气不完整 | 超出天数标记不可用，提示出行前复查，不编造 |
| 会话存内存 | 重启丢失 | 第一期接受；后续可换 SQLite |
| Tavily 免费额度 | 高频使用可能耗尽 | 控制搜索次数，后续加缓存 |
| LLM 生成 JSON 不稳定 | 行程解析失败 | 校验 + 只修复一次；失败明确报错，不伪造兜底 |
| 模型自由调用工具不可控 | 可能提前搜索或死循环 | 工具由控制器按槽位触发，硬限制 6 次 |
| 代理客户端关闭 | git 无法访问 GitHub | 保持 `127.0.0.1:12450` 运行 |
| `.env` 含真实密钥 | 误提交会泄露 | 已 gitignore；每次提交前检查 |

---

## 六、下一步（按顺序）

1. **Task 1**：创建 `.venv`、`requirements.txt`、`app/config.py` 及其测试
2. **Task 2-6**：数据模型、预算、天气、景点、槽位
3. **Task 7**：ChatAgent 与提示词（核心）
4. **Task 8-9**：会话存储、FastAPI + SSE
5. **Task 10**：前端页面
6. **Task 11**：端到端测试、真实冒烟、README
7. 每完成一个任务：跑测试 → 提交 → 推送
8. 全部完成后更新本文件

---

## 七、恢复工作的方法

新会话中按以下顺序阅读：

1. 本文件 `PROGRESS.md`
2. 设计文档 `docs/superpowers/specs/2026-11-07-travel-agent-design.md`
3. 实现计划 `docs/superpowers/plans/2026-11-07-travel-agent.md`
4. 从计划的 **Task 1** 开始执行

### 环境自检

```powershell
python --version
python -c "import openai, dotenv; print('deps ok')"
git --version
gh auth status
```

### 仓库自检

```powershell
git -C "C:\Users\ASUS\Desktop\travel-agent" status -sb
git -C "C:\Users\ASUS\Desktop\travel-agent" log --oneline -3
```

### 密钥自检（不打印密钥）

```powershell
# Tavily
python -c "import os; from dotenv import load_dotenv; load_dotenv(r'C:\Users\ASUS\Desktop\travel-agent\.env'); import urllib.request, json; k=os.environ['TAVILY_API_KEY']; req=urllib.request.Request('https://api.tavily.com/search', data=json.dumps({'api_key':k,'query':'test','max_results':1}).encode(), headers={'Content-Type':'application/json'}); print('tavily', urllib.request.urlopen(req, timeout=30).status)"
```

```powershell
# DeepSeek
python -c "import os; from dotenv import load_dotenv; load_dotenv(r'C:\Users\ASUS\Desktop\travel-agent\.env'); from openai import OpenAI; c=OpenAI(api_key=os.environ['DEEPSEEK_API_KEY'], base_url=os.environ['DEEPSEEK_BASE_URL']); r=c.chat.completions.create(model=os.environ['DEEPSEEK_MODEL'], messages=[{'role':'user','content':'hi'}], max_tokens=5); print('deepseek ok')"
```

### 提交与推送

```powershell
$proj = "C:\Users\ASUS\Desktop\travel-agent"
git -C $proj add -A
git -C $proj commit -m "feat: ..."
git -C $proj push origin main
```

> 推送前务必确认 `git status` 中没有 `.env`。
