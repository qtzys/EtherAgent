# EtherAgent · 最核心的 6 能力 Agent

> 基于 `01-设计/04-Agent架构.md` v0.4 决策，构建的**最核心 6 能力**可运行原型。
>
> 页面设计：仿照腾讯 **WorkBuddy** 桌面 Agent 风格（微信绿 `#07c160`）。

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](#license)
[![Version](https://img.shields.io/badge/version-v0.2-orange)](./TODO.md)
[![Status](https://img.shields.io/badge/status-running-success)](#quick-start)

---

## ✨ 核心亮点（v0.2）

- **6 项核心能力** × **18 个最核心子能力**——覆盖感知/思考/记忆/行动/表达/协作
- **5 个 P0 全部完成**：真 LLM / 审计日志 / SQLite 持久化 / Memory 重要性 / Belief State
- **ReAct 主循环**：思考 ⇄ 行动，支持失败检测与死循环退出
- **流式输出**：SSE 实时推送给前端
- **双 LLM**：内置 `MockLLM`（免 key 即可跑）+ `RealLLM`（Anthropic SDK，支持自定义 base_url）
- **持久化**：单一 SQLite + WAL 模式，启动自动恢复任务
- **页面**：仿 WorkBuddy 桌面布局，任务列表 / 实时对话 / 流式 markdown

完整待办清单：[`TODO.md`](./TODO.md)

---

## 📑 目录

- [快速开始](#quick-start)
- [架构概览](#architecture)
- [项目结构](#project-structure)
- [6 核心能力](#capabilities)
- [API 参考](#api-reference)
- [配置说明](#configuration)
- [Roadmap](#roadmap)
- [常见问题](#faq)
- [License](#license)

---

## Quick Start

### 1. 准备环境

```bash
# Python 3.10+
python --version

# 安装依赖
cd 核心Agent
pip install -r requirements.txt
```

### 2. 启动服务（Mock LLM 模式）

```bash
python server.py
```

打开浏览器：**http://localhost:8000**

> Mock 模式无需任何 API key，可立即体验所有能力。

### 3. （可选）切换到真 LLM

```bash
# 复制配置模板
cp .env.example .env

# 编辑 .env，填入你的 Anthropic API key
# ANTHROPIC_API_KEY=sk-ant-xxxxxxxx
# ANTHROPIC_BASE_URL=https://api.anthropic.com   # 或兼容代理
# LLM_MODEL=claude-sonnet-4-6
# LLM_MAX_TOKENS=4096
```

或者通过前端配置页 `http://localhost:8000` 里的"LLM 配置"面板**运行时**填入 key（仅存内存，不写文件）。

---

## Architecture

```
            用户消息
               │
               ▼
        ┌─────────────┐
        │   Perceive  │  ← 输入接收 / 行动结果回流
        └──────┬──────┘
               │
               ▼
        ┌─────────────┐
   ┌───→│    Think    │  ← ReAct：基于 observation + memory + belief 决策
   │    │  (LLM 调用) │
   │    └──────┬──────┘
   │           │
   │      Decision: call_tool / answer / fail
   │           │
   │           ▼
   │    ┌─────────────┐         ┌──────────────┐
   │    │   Remember  │←────────│   Belief     │  ← 信念状态 + 校准
   │    │  (编码+检索) │         │  (自举+更新)  │
   │    └─────────────┘         └──────────────┘
   │           │
   │           ▼
   │    ┌─────────────┐
   │    │     Act     │  ← 工具调用（含失败回滚）
   │    └──────┬──────┘
   │           │
   │           └──→ 工具结果回流 → Perceive (下一轮)
   │
   └─── 若 Decision = answer → Express (流式输出) → 结束
```

主循环伪代码：

```python
while not finished:
    decision = think(observation, memory_summary, belief_summary)
    if decision == "fail" or dead_loop: return failure
    if decision == "answer": stream(decision.content); return success
    if decision == "call_tool": execute(tool); observe(result); reinforce(belief)
```

---

## Project Structure

```
核心Agent/
├── server.py                 # FastAPI 入口（路由 + SSE）
├── requirements.txt          # 依赖
├── .env.example              # 环境变量模板（不含真实 key）
├── README.md
├── TODO.md                   # 待办清单（42+ 未做项）
│
├── agent/                    # 6 核心能力 + 基础设施
│   ├── __init__.py
│   ├── core.py               # Agent 主类（ReAct 主循环）
│   ├── perceive.py           # ① 感知
│   ├── think.py              # ② 思考（Decision dataclass + 失败检测）
│   ├── remember.py           # ③ 记忆（编码 + 三维检索 + reinforce）
│   ├── act.py                # ④ 行动（ToolRegistry + 工具调用）
│   ├── express.py            # ⑤ 表达（流式输出）
│   ├── collaborate.py        # ⑥ 协作（A2A）
│   ├── llm.py                # LLM 抽象 + MockLLM + RealLLM
│   ├── audit.py              # 审计日志（10 种 action）
│   ├── storage.py            # SQLite 持久化（WAL）
│   └── belief.py             # 信念状态（自举 + 校准 + 注入）
│
├── tools/                    # 工具集
│   ├── __init__.py
│   └── builtin.py            # 5 个内置工具
│
└── web/                      # 仿 WorkBuddy 前端
    ├── index.html
    ├── style.css
    └── app.js
```

---

## Capabilities

| # | 能力 | v0.2 已做子能力 | 来源 |
|---|---|---|---|
| 🟢 | **感知** Perceive | 输入接收 / 行动结果回流 | — |
| 🔵 | **思考** Think | ReAct 单步推理 / 失败检测（死循环 + max_iterations）/ Belief 校准 | Agent-Pro |
| 🟡 | **记忆** Remember | 编码 / 三维检索 / 遗忘 / **重要性打分** / **跨 session 持久化** | Generative Agents |
| 🟠 | **行动** Act | 工具调用 / 失败回滚 | — |
| 🟣 | **表达** Express | 流式输出 / 结构化结果（Markdown + JSON） | — |
| 🔴 | **协作** Collaborate | A2A 调用 / 被调用接口 | MetaGPT |

### 内置工具（5 个）

| 工具 | 触发关键词 | 用途 |
|---|---|---|
| `search_web` | 搜索 / 查一下 / 上网 | 联网搜索（mock 返回） |
| `read_file` | 读取 / 打开 / 看 .md/.txt/.py | 读文件 |
| `write_file` | 写文件 / 创建 / 保存 | 写文件 |
| `run_command` | 执行 / 运行 / ls / dir / pwd | 跑命令（仅白名单只读命令） |
| `call_sub_agent` | 让...做 / 交给 / 调用 agent | 调 sub-agent |

---

## API Reference

服务启动后访问 `http://localhost:8000/docs` 看 OpenAPI 自动生成的完整文档。

### 核心端点

| 方法 | 路径 | 用途 |
|---|---|---|
| `GET` | `/api/info` | Agent 自我描述 |
| `POST` | `/api/chat` | **发消息（SSE 流式）** |
| `GET` | `/api/tasks` | 任务列表 |
| `DELETE` | `/api/tasks/{id}` | 删除单个任务 |
| `DELETE` | `/api/tasks` | 清空所有任务 |
| `GET` | `/api/tools` | 当前可用工具列表 |

### 调试 / 运维端点

| 方法 | 路径 | 用途 |
|---|---|---|
| `GET` / `POST` | `/api/llm/config` | 查看 / 设置 LLM（key 仅存内存） |
| `POST` | `/api/llm/test` | LLM 连通性测试 |
| `GET` / `DELETE` | `/api/audit/logs` | 查询 / 清空审计日志 |
| `GET` | `/api/audit/stats` | 数据库统计 |
| `GET` / `POST` | `/api/memory/list` | 记忆列表 |
| `POST` | `/api/memory/retrieve` | 三维检索记忆 |
| `GET` / `POST` / `DELETE` | `/api/beliefs[/{key}]` | 信念状态 CRUD |
| `POST` | `/api/beliefs/{key}/calibrate` | 信念校准 |
| `GET` | `/api/beliefs/prompt` | LLM 视角的信念提示 |

### SSE 事件类型（`POST /api/chat`）

```
data: {"type":"task_start","task_id":"..."}
data: {"type":"perceive","observation":{...}}
data: {"type":"thinking","reasoning":"..."}
data: {"type":"tool_call","tool":"...","args":{...}}
data: {"type":"tool_result","success":true,"result":{...}}
data: {"type":"text_chunk","text":"..."}    ← 流式文本
data: {"type":"answer","content":"..."}
data: {"type":"file","path":"..."}
data: {"type":"task_end","status":"已完成"}
```

---

## Configuration

### 环境变量（`.env`）

| 变量 | 必填 | 默认 | 说明 |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | 否 | (空) | Anthropic API key；空则用 MockLLM |
| `ANTHROPIC_BASE_URL` | 否 | (空) | 自定义 base_url（兼容代理） |
| `LLM_MODEL` | 否 | `claude-sonnet-4-6` | 模型名 |
| `LLM_MAX_TOKENS` | 否 | `4096` | 单次响应最大 token |

> ⚠️ **永远不要把 `.env` 提交到 git**（已在 `.gitignore` 中）。

### SQLite 数据库

- 默认路径：`<项目根>/agent.db`
- 表：`tasks` / `memories` / `beliefs` / `audit_logs`
- 启动自动建表 + WAL 模式
- 想完全重置：删除 `agent.db*` 三个文件后重启

---

## Roadmap

完整待办：[`TODO.md`](./TODO.md)（42+ 未做项）

### P0 · v0.2 已完成 ✅
- 接入真 LLM / 审计日志 / 跨 session 持久化 / Belief State / Memory 重要性打分

### P1 · 建议下个迭代
- SKILL.md 格式支持（行业事实标准）
- Gateway 单一入口
- Failure Attribution（解决"找不到根因"）
- 多 Agent 编排（Leader / Worker / Verifier）
- 反思作为记忆（闭环）

### P2 · 远期
- 多模态输入输出（image / audio / file）
- 自我进化（Memory 整理 / Skill 蒸馏）
- 跨进程 / 跨平台

---

## FAQ

### Q: 为什么用 SQLite 而不是 Postgres / Redis？
A: v0 追求"开箱即跑、零依赖"。SQLite 单文件足够 demo；生产环境可平滑切换到 Postgres（`storage.py` 已抽象）。

### Q: Belief State 有什么实际用途？
A: 让 Agent 知道自己"在做什么、能做什么、信什么"。例如：
- 工具连续失败 → 自动降低 `self.tools` 置信度 → 切换备选工具
- 用户偏好简短回答 → `user.preference` 信念 → 注入 LLM prompt

### Q: 怎么扩展新工具？
A: 在 `tools/builtin.py` 里加一个继承 `Tool` 的类，然后 `register_builtin_tools` 注册即可。Agent 启动时会自动注入到 LLM 的工具列表。

### Q: 接入 OpenAI / 其他模型？
A: 在 `agent/llm.py` 继承 `LLM` 抽象类，实现 `decide(observation, memory_summary, available_tools)` 即可。RealLLM 是 Anthropic 实现参考。

---

## License

MIT