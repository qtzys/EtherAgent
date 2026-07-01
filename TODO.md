# 最核心 Agent v0 · 待办清单（TODO / NOT-DONE）

> **写作日期**：2026-07-01（v0.2 增量更新）
> **文档定位**：v0 只做了 6 个核心能力的"最小子能力"。本文档列出**所有没做、待做、做了一半**的能力，方便后续 review。
>
> **架构对应**：本待办对照 `01-设计/04-Agent架构.md`（35 项完整能力清单）+ `01-设计/06-竞品分析.md`（v1 借鉴清单）。
>
> **v0.2 增量**：已完成 5 个 P0 → 详见 §11

---

## 0. 总览

| 类别 | v0 已做 | v0 没做 | 待做总数 |
|---|---|---|---|
| **6 核心能力** | 13 个最核心子能力 | 28 个 | 详见 §1 |
| **7 候选能力（v0 不在范围）** | 0 | 7 | 详见 §2 |
| **4 架构基础（v0 不在范围）** | 0 | 4 | 详见 §3 |
| **2 元能力（v0 不在范围）** | 0 | 2 | 详见 §4 |
| **LLM 真接入** | Mock | 1 | 详见 §5 |
| **安全 / 沙箱** | 部分 | 多个 | 详见 §6 |
| **总计** | **13** | **42+** | — |

---

## 1. 6 核心能力的待办子能力（v0 没做的）

### 1.1 🟢 感知（Perceive）· 已做 2/5

| # | 子能力 | 状态 | 备注 |
|---|---|---|---|
| ① | 输入接收 | ✅ v0 | 文本消息 |
| ② | 行动结果回流 | ✅ v0 | 工具结果观察 |
| ③ | **多模态输入** | ❌ 待做 | image / audio / file |
| ④ | **环境状态观察** | ❌ 待做 | 读 Memory / Belief 快照 |
| ⑤ | **感知过滤器** | ❌ 待做 | 屏蔽噪音、优先级排序 |

### 1.2 🔵 思考（Think）· 已做 2/8

| # | 子能力 | 状态 | 备注 |
|---|---|---|---|
| ① | 单步推理（ReAct） | ✅ v0 | Mock LLM 决策 |
| ② | 失败检测 | ✅ v0 | 死循环 + max_iterations |
| ③ | **多步规划** | ❌ 待做 | Plan-and-Execute |
| ④ | **思维模式切换** | ❌ 待做 | ReAct / ToT / Reflection / Plan-Execute |
| ⑤ | **多模型集成** | ❌ 待做 | Ensemble（多模型投票） |
| ⑥ | **反思** | ❌ 待做 | self-critique / failure-driven |
| ⑦ | **Belief State 校准** | ❌ 待做 | 来自论文 Agent-Pro |
| ⑧ | **搜索式规划** | ❌ 待做 | DFS / BFS / MCTS |

### 1.3 🟡 记忆（Remember）· 已做 3/9

| # | 子能力 | 状态 | 备注 |
|---|---|---|---|
| ① | 编码 | ✅ v0 | append to deque |
| ② | 检索（全部） | ✅ v0 | v0 = 返回全部；TODO = 向量检索 |
| ③ | 遗忘 | ✅ v0 | deque 自动滚动 |
| ④ | **重要性打分** | ❌ 待做 | 来自论文 Generative Agents |
| ⑤ | **三维检索** | ❌ 待做 | 最近性 / 重要性 / 相关性 |
| ⑥ | **跨 session 持久化** | ❌ 待做 | v0 单 session；TODO = SQLite |
| ⑦ | **反思作为记忆** | ❌ 待做 | reflection as memory type |
| ⑧ | **多层记忆** | ❌ 待做 | L1 Working / L2 Short / L3 Episodic / L4 Semantic / L5 Procedural |
| ⑨ | **Belief State** | ❌ 待做 | Agent 显式建模自我 / 环境 / 任务 |

### 1.4 🟠 行动（Act）· 已做 2/7

| # | 子能力 | 状态 | 备注 |
|---|---|---|---|
| ① | 工具调用 | ✅ v0 | 通过 ToolRegistry |
| ② | 失败回滚 | ✅ v0 | try/except，不阻塞 |
| ③ | **Side Effect Tracking** | ❌ 待做 | before/after 对比，可回滚 |
| ④ | **细粒度权限** | ❌ 待做 | auto / ask / deny 三态 |
| ⑤ | **高风险 HITL** | ❌ 待做 | 危险操作强制人工确认 |
| ⑥ | **沙箱执行** | ❌ 待做 | Docker / SSH / OpenShell（v0 仅允许只读命令） |
| ⑦ | **Toolset 系统** | ❌ 待做 | 工具分类管理（MCP 协议） |

### 1.5 🟣 表达（Express）· 已做 2/6

| # | 子能力 | 状态 | 备注 |
|---|---|---|---|
| ① | 流式输出 | ✅ v0 | 按 chunk 切分 |
| ② | 结构化结果 | ✅ v0 | Markdown + JSON |
| ③ | **多模态输出** | ❌ 待做 | image / audio / file 生成 |
| ④ | **引用 / cite** | ❌ 待做 | 每个事实带 source |
| ⑤ | **格式自适应** | ❌ 待做 | 按 channel 不同格式 |
| ⑥ | **偏好驱动风格** | ❌ 待做 | 简洁 / 详细 / 正式 / 口语 |

### 1.6 🔴 协作（Collaborate）· 已做 2/8

| # | 子能力 | 状态 | 备注 |
|---|---|---|---|
| ① | A2A 调用 | ✅ v0 | sub_agents dict |
| ② | 被调用接口 | ✅ v0 | handle_call / as_tool_definition |
| ③ | **MCP 协议** | ❌ 待做 | 外部工具协议（事实标准） |
| ④ | **多 Agent 编排** | ❌ 待做 | Leader/Worker/Verifier（Mavis 模式） |
| ⑤ | **复杂拓扑** | ❌ 待做 | Blackboard / 树形 / 网状 |
| ⑥ | **跨平台** | ❌ 待做 | 跨进程 / 跨机器 |
| ⑦ | **8 原语** | ❌ 待做 | discover / call / subscribe / handoff / cancel / result / heartbeat / vote |
| ⑧ | **结构化消息 Schema** | ❌ 待做 | 来自论文 MetaGPT，强 schema 不是 free-form |

---

## 2. 7 候选能力（v0 完全没做 · 不在范围）

> 这些是你文档 v0.4 里 v1/v2/v3 才考虑的能力，v0 不做。

| # | 能力 | 来源 | 排期 |
|---|---|---|---|
| 13 | **目标** Purpose | v0.2 人维度推导 | v1 |
| 14 | **主动** Will | v0.2 人维度推导 | v2 |
| 15 | **价值** Values | v0.2 人维度推导 | v1 |
| 16 | **偏好** Preferences | v0.2 人维度推导 | v2 |
| 17 | **直觉** Intuition | v0.2 人维度推导 | v2 |
| 18 | **关系** Relationships | v0.2 人维度推导 | v3+ |
| 19 | **角色** Roles | v0.2 人维度推导 | v3+ |

---

## 3. 4 架构基础（v0 完全没做 · 不在范围）

> 来自竞品分析 `06-竞品分析.md`，行业 v1 必备。v0 不实现，但 UI / 代码已留好接入点。

| # | 架构基础 | 行业来源 | 排期 |
|---|---|---|---|
| **A1** | **SKILL.md 格式** | Anthropic + Hermes + WorkBuddy | v1 |
| **A2** | **Gateway 单一入口** | OpenClaw + Hermes | v1 |
| **A3** | **P0 退化检测** | Hermes + Mavis | v1 |
| **A4** | **审计日志** | OpenClaw + WorkBuddy | v1 |

---

## 4. 2 元能力（v0 完全没做）

| # | 元能力 | 排期 |
|---|---|---|
| 1 | **退化检测（P0 进化前置）** | v1 必备 |
| 2 | **HITL 治理** | v2+ |

---

## 5. LLM 真接入（v0 是 Mock）

| # | 子能力 | 状态 | 备注 |
|---|---|---|---|
| 1 | **MockLLM（关键词模式匹配）** | ✅ v0 | 不需要 API key 即可运行 |
| 2 | **RealLLMSkeleton（接入 Claude / OpenAI）** | ❌ 待做 | `agent/llm.py` 已留接口，实现 decide() 即可 |

### MockLLM 的限制（用户须知）

- **触发词有限**：仅识别 "搜索/读取/写文件/执行/让...做" 等关键词
- **回答模板化**：未匹配的输入会得到通用兜底回复
- **不真"思考"**：决策靠模式匹配，不是真推理

**→ 真正使用时，强烈建议接入真 LLM**

---

## 6. 安全 / 沙箱（v0 仅做了最简版）

| # | 安全项 | v0 状态 | v1 应该做 |
|---|---|---|---|
| 1 | **沙箱执行** | ❌ 仅允许只读命令（ls/dir/pwd/echo/cat/whoami/date） | Docker / SSH / OpenShell |
| 2 | **权限控制** | ❌ 无 | auto / ask / deny 三态 |
| 3 | **HITL** | ❌ 无 | 高风险操作人工确认 |
| 4 | **审计日志** | ❌ 无（仅 task 记录） | 所有 action 完整日志 |
| 5 | **凭证管理** | ❌ 无 | 单独的 CredentialPool |
| 6 | **速率限制** | ❌ 无 | token / RPM 限制 |
| 7 | **超时控制** | ⚠️ 部分（subprocess 10s） | 全局超时 |

---

## 7. 工程级 TODO（v0 简化处理的地方）

| # | 工程项 | v0 状态 | v1 应该做 |
|---|---|---|---|
| 1 | **测试** | ❌ 无 | pytest 单元测试 + 集成测试 |
| 2 | **类型检查** | ⚠️ 部分（dataclass） | mypy strict mode |
| 3 | **错误处理** | ⚠️ 基础 | 分类错误 + retry 策略 |
| 4 | **日志系统** | ⚠️ print | 结构化日志（loguru / structlog） |
| 5 | **配置管理** | ❌ 硬编码 | pydantic-settings + .env |
| 6 | **打包** | ❌ 源码运行 | pyproject.toml + Docker |
| 7 | **API 文档** | ⚠️ FastAPI 自动 | OpenAPI + 文档站 |
| 8 | **多用户隔离** | ❌ 单 Agent 全局 | session 管理 + 权限 |

---

## 8. 用户体验 TODO（v0 是 Demo 级）

| # | UX 项 | v0 状态 | 改进方向 |
|---|---|---|---|
| 1 | **响应式布局** | ⚠️ 桌面优先 | 移动端适配 |
| 2 | **Markdown 渲染** | ❌ 纯文本 | 渲染为富文本 |
| 3 | **代码高亮** | ❌ 无 | highlight.js |
| 4 | **深色模式** | ❌ 无 | 暗色主题 |
| 5 | **快捷键** | ❌ 仅 Enter 发送 | Ctrl+K 新建 / Ctrl+L 清空 |
| 6 | **历史搜索** | ❌ 无 | 任务列表搜索 |

---

## 9. 论文基线（02-论文基线.md）建议补入的能力（v0 完全没做）

| # | 能力 | 来源论文 | 排期 |
|---|---|---|---|
| 1 | **Belief State** 一等公民 | Agent-Pro | v1+（关键盲点） |
| 2 | **Failure Attribution** | LIFE | v2+（关键盲点） |
| 3 | **SOP Engine** | MetaGPT | v2+（关键盲点） |
| 4 | **Ensemble as 一等子能力** | More Agents Is All You Need | v2+ |
| 5 | **Memory 重要性打分 + 三维检索** | Generative Agents | v1+ |
| 6 | **反思作为记忆** | Generative Agents / Reflexion | v1+ |
| 7 | **抽象级反思** | Reflexion | v2+ |
| 8 | **HITL Agent 抽象** | AutoGen | v2+ |
| 9 | **分层协调器** | Large-Scale RL | v3+ |
| 10 | **协作放大错误防御** | LIFE | v2+ |

---

## 10. 下一步建议（按优先级）

### 🔴 P0 · v1 之前必须做
1. **接入真 LLM**（Claude / OpenAI）—— Mock 只能 demo
2. **审计日志** —— 安全基础
3. **跨 session 持久化（SQLite）** —— 不重启就丢记忆
4. **Belief State 最小版** —— 解决"自信地做错事"
5. **Memory 重要性打分** —— 检索效率

### 🟠 P1 · v2 之前做
6. **SKILL.md 格式支持** —— 行业事实标准
7. **Gateway 单一入口** —— 架构清晰
8. **Failure Attribution** —— 解决"找不到根因"
9. **多 Agent 编排（Leader/Worker/Verifier）** —— Mavis 模式
10. **反思作为记忆** —— 闭环

### 🟡 P2 · 后续
11. 多模态输入输出
12. 跨进程 / 跨平台
13. 自我进化（E1 Memory 整理 / E2 Skill 蒸馏）
14. 12 个社会能力（万级 Agent 时）
15. Belief 校准 / DFS 搜索

---

## 11. v0.2 增量（5 P0 完成）

> **2026-07-01 增量**：5 个 P0 全部完成，v0 → v0.2。

### 11.1 P0-1：接入真 LLM（Claude / OpenAI）✅

- **文件**：`agent/llm.py`（`RealLLM` 类）
- **能力**：通过 anthropic SDK 接入，支持 `ANTHROPIC_API_KEY` env var + 运行时 `POST /api/llm/config` 切换 + `GET /api/llm/test` 连通性测试
- **fallback**：若 key 未设置，自动用 `MockLLM`（关键词模式匹配），不影响 demo

### 11.2 P0-2：审计日志 ✅

- **文件**：`agent/audit.py` + `agent/storage.py`（`audit_logs` 表）
- **能力**：记录 task.start/end、tool.call/result、llm.call/config/test、belief.set/update、memory.save、api.request
- **API**：`GET /api/audit/logs?action=...&limit=...` + `DELETE /api/audit/logs` + `GET /api/audit/stats`

### 11.3 P0-3：跨 session 持久化（SQLite）✅

- **文件**：`agent/storage.py`
- **4 张表**：tasks / memories / beliefs / audit_logs
- **WAL 模式**：高并发读不阻塞写
- **启动恢复**：`Agent._load_tasks_from_storage()` 自动恢复历史任务

### 11.4 P0-4：Memory 重要性打分 ✅

- **文件**：`agent/remember.py`（DEFAULT_IMPORTANCE 表）+ `agent/storage.py`（retrieve_memories 三维加权）
- **打分规则**：
  - `tool_failure = 0.8`（失败值得反思）
  - `reflection = 0.9`
  - `belief_update = 0.85`
  - 内容长度 >200 字符 +0.1
- **三维检索**：recency(0.3) + importance(0.4) + relevance(0.3) 加权得分
- **reinforce()**：每次访问 +0.05

### 11.5 P0-5：Belief State 最小版 ✅

- **文件**：`agent/belief.py` + `agent/storage.py`（`beliefs` 表）
- **核心能力**：
  - 自举：self.name/version/capabilities/tools + env.cwd/os/timezone + task.current/history_length + session.id
  - CRUD：`get(key)` / `set(key, value, confidence, evidence)` / `list_all()` / `delete(key)`
  - 校准：`update_confidence(key, delta, evidence)`（成功 +0.05 / 失败 -0.1 / 用户纠正 -0.2）
  - 注入：`to_prompt()` 把信念状态按 priority + confidence 排序后塞进 LLM
  - 工具反馈：`record_tool_outcome(tool, success)` 自动调整 `self.tools` 和 `task.current` 信念
- **API**：
  - `GET /api/beliefs` - 列表
  - `GET /api/beliefs/{key}` - 单条
  - `GET /api/beliefs/stats` - 统计
  - `GET /api/beliefs/prompt` - LLM 视角的提示
  - `POST /api/beliefs` - 设置（key + value + confidence + evidence）
  - `POST /api/beliefs/{key}/calibrate?delta=...&evidence=...` - 校准
  - `DELETE /api/beliefs/{key}` - 删除

### 11.6 v0.2 新增任务能力清单（相比 v0）

| 能力 | v0.1 | v0.2 |
|---|---|---|
| 任务删除 | ❌ | ✅（`DELETE /api/tasks/{id}` + `DELETE /api/tasks`） |
| 真 LLM | ❌ | ✅（RealLLM + 运行时切换） |
| 审计 | ❌ | ✅（10 种 action 分类） |
| 持久化 | ❌ | ✅（SQLite WAL） |
| Memory 重要性 | ❌ | ✅（自动打分 + 三维检索） |
| Belief State | ❌ | ✅（自举 + 校准 + 注入） |

**v0.2 总计 = 18 个子能力**（v0.1 = 13，+5 P0）

---

## 文档结束

**v0.2 已做**：18 个最核心子能力（6 能力的最小集 + P0 五个）+ 5 个内置工具 + 双 LLM（Mock / Real）+ SQLite 持久化 + 仿 WorkBuddy 页面

**v0.2 没做**：~42+ 个能力 / 工程项（详见 §1~§9）

**→ 任何 v1 决策前，回看此 TODO，决定哪些补入**

---

> **建议节奏**：v0.2 → demo + 验证 → v1 = 当前 v0.2 + §3 的 4 架构基础 → v2 = + §2 的 2 候选 + 部分 P1 → v3+ = 全部 35 项