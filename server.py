"""
FastAPI 服务器 · 入口

启动：
    pip install -r requirements.txt
    python server.py
    # 打开 http://localhost:8000

端点：
    GET  /                          → 静态页面
    GET  /api/tasks                 → 所有任务列表
    POST /api/chat                  → 发消息（流式 SSE）
    GET  /api/tasks/{task_id}       → 单个任务详情
    GET  /api/tools                 → 当前可用工具列表
    GET  /api/info                  → Agent 自我描述
"""

import json
import os
import sys
from pathlib import Path

# 让 server.py 可以 import agent/ 和 tools/
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

# 加载 .env（如果存在）
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent import Agent
from agent.llm import RealLLM, MockLLM

app = FastAPI(title="最核心 Agent v0", version="0.2.0")

# 单 Agent 实例（v0 = 全局共享；多用户 v1 再加 session 隔离）
agent = Agent()


def _create_llm():
    """根据环境变量创建 LLM。
    优先用 RealLLM（如果 ANTHROPIC_API_KEY 已设置），否则 MockLLM。
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if api_key:
        try:
            return RealLLM(api_key=api_key)
        except Exception as e:
            print(f"[Agent] RealLLM init failed, fallback to MockLLM: {e}")
            return MockLLM()
    return MockLLM()


# 用环境变量初始化 LLM
agent.think.llm = _create_llm()

# 静态文件
app.mount("/static", StaticFiles(directory=str(ROOT / "web")), name="static")


# ============= 页面 =============
@app.get("/", response_class=HTMLResponse)
async def index():
    return (ROOT / "web" / "index.html").read_text(encoding="utf-8")


# ============= API =============
@app.get("/api/info")
async def api_info():
    """Agent 自我描述。"""
    return {
        "name": "最核心 Agent v0",
        "version": "0.1.0",
        "capabilities": {
            "perceive":     "感知（输入接收 / 行动回流）",
            "think":        "思考（ReAct 单步推理 + 失败检测）",
            "remember":     "记忆（编码 / 检索 / 遗忘，单会话）",
            "act":          "行动（工具调用 + 失败回滚）",
            "express":      "表达（流式输出 + 结构化结果）",
            "collaborate":  "协作（A2A 调用 / 被调用接口）",
        },
        "tools": agent.tool_registry.list_tools(),
        "llm": type(agent.think.llm).__name__,
    }


@app.get("/api/tasks")
async def api_tasks():
    return {"tasks": agent.list_tasks()}


@app.get("/api/tasks/{task_id}")
async def api_task(task_id: str):
    task = agent.get_task(task_id)
    if not task:
        return {"error": "task not found"}
    return task


@app.delete("/api/tasks/{task_id}")
async def api_delete_task(task_id: str):
    """删除指定任务。"""
    success = agent.delete_task(task_id)
    if not success:
        return {"error": "task not found", "deleted": False}
    return {"deleted": True, "task_id": task_id}


@app.delete("/api/tasks")
async def api_clear_tasks():
    """清空所有任务。"""
    n = agent.clear_tasks()
    return {"cleared": n}


@app.get("/api/tools")
async def api_tools():
    return {"tools": agent.tool_registry.list_tools()}


class LLMConfigRequest(BaseModel):
    api_key: str
    base_url: str | None = None
    model: str | None = None


@app.get("/api/llm/config")
async def api_get_llm_config():
    """获取当前 LLM 配置（不返回完整 key，只返回是否配置 + 模型名）。"""
    llm = agent.think.llm
    return {
        "type": type(llm).__name__,
        "is_configured": llm.is_configured() if hasattr(llm, "is_configured") else True,
        "model": getattr(llm, "model", ""),
        "base_url": getattr(llm, "base_url", "") or "(默认)",
    }


@app.post("/api/llm/config")
async def api_set_llm_config(req: LLMConfigRequest):
    """运行时设置 LLM（key 仅存在内存，不写入文件）。
    如果当前是 MockLLM，会自动升级为 RealLLM。
    """
    llm = agent.think.llm
    if not isinstance(llm, RealLLM):
        # 升级 Mock → Real
        new_llm = RealLLM(api_key=req.api_key, base_url=req.base_url, model=req.model)
        agent.think.llm = new_llm
        llm = new_llm
    else:
        llm.set_api_key(api_key=req.api_key, base_url=req.base_url, model=req.model)
    return {
        "ok": True,
        "type": type(llm).__name__,
        "model": llm.model,
        "base_url": llm.base_url or "(默认)",
        "note": "API key 仅保存在内存，不写入文件。重启服务需重新设置。",
    }


@app.post("/api/llm/test")
async def api_test_llm():
    """测试当前 LLM 是否能连通。"""
    llm = agent.think.llm
    if not isinstance(llm, RealLLM):
        return {"ok": False, "error": "当前是 MockLLM，无 API key"}
    try:
        # 用最简单的问题测试
        from agent.think import Decision
        test_obs = {"type": "user_input", "content": "ping"}
        decision = llm.decide(
            observation=test_obs,
            memory_summary="(test)",
            available_tools=[],
        )
        return {
            "ok": True,
            "model": llm.model,
            "decision_action": decision.action,
            "content_preview": decision.content[:100] if decision.content else "",
        }
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


# ============= 审计日志 API =============
@app.get("/api/audit/logs")
async def api_audit_logs(action: str | None = None, limit: int = 100):
    """查询审计日志。"""
    return {"logs": agent.audit.recent(action=action, limit=limit)}


@app.get("/api/audit/stats")
async def api_audit_stats():
    """数据库统计。"""
    return agent.storage.stats()


@app.delete("/api/audit/logs")
async def api_audit_clear():
    """清空审计日志（仅用于测试）。"""
    n = agent.storage.clear_audit_logs()
    return {"cleared": n}


# ============= 记忆 API =============
@app.get("/api/memory/stats")
async def api_memory_stats():
    """记忆统计。"""
    return agent.remember.stats()


@app.get("/api/memory/list")
async def api_memory_list(session_id: str | None = None, limit: int = 50):
    """列出持久化记忆。"""
    sid = session_id or agent.remember.session_id
    return {"memories": agent.storage.list_memories(sid, limit=limit)}


class RetrieveRequest(BaseModel):
    query: str | None = None
    top_k: int = 5


@app.post("/api/memory/retrieve")
async def api_memory_retrieve(req: RetrieveRequest):
    """三维检索记忆。"""
    results = agent.storage.retrieve_memories(
        session_id=agent.remember.session_id,
        query=req.query,
        top_k=req.top_k,
    )
    return {"results": results}


@app.delete("/api/memory")
async def api_memory_clear():
    """清空记忆（仅当前 session）。"""
    n = agent.remember.clear_all()
    return {"cleared": n}


# ============= 信念状态 API =============
@app.get("/api/beliefs")
async def api_beliefs_list():
    """列出所有信念。"""
    return {"beliefs": agent.belief.list_all()}


@app.get("/api/beliefs/stats")
async def api_beliefs_stats():
    """信念统计。"""
    return agent.belief.stats()


@app.get("/api/beliefs/prompt")
async def api_belief_prompt():
    """信念状态转 LLM prompt 片段（调试用）。"""
    return {"prompt": agent.belief.to_prompt()}


@app.get("/api/beliefs/{key}")
async def api_belief_get(key: str):
    """获取单条信念。"""
    b = agent.belief.get(key)
    if not b:
        return {"error": "belief not found"}
    return b


class BeliefUpsertRequest(BaseModel):
    key: str
    value: str
    confidence: float = 0.7
    evidence: str = ""


@app.post("/api/beliefs")
async def api_belief_set(req: BeliefUpsertRequest):
    """设置/更新一条信念。"""
    try:
        agent.belief.set(
            key=req.key,
            value=req.value,
            confidence=req.confidence,
            evidence=req.evidence,
        )
        agent.audit.belief_set(key=req.key, confidence=req.confidence)
        return {"ok": True, "key": req.key}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/beliefs/{key}/calibrate")
async def api_belief_calibrate(key: str, delta: float = 0.05, evidence: str = ""):
    """调整某条信念的 confidence。"""
    ok = agent.belief.update_confidence(key=key, delta=delta, evidence=evidence)
    if not ok:
        return {"error": "belief not found"}
    b = agent.belief.get(key)
    return {"ok": True, "key": key, "new_confidence": b["confidence"] if b else None}


@app.delete("/api/beliefs/{key}")
async def api_belief_delete(key: str):
    """删除一条信念。"""
    ok = agent.belief.delete(key)
    if not ok:
        return {"error": "belief not found"}
    return {"deleted": True, "key": key}


class ChatRequest(BaseModel):
    message: str


@app.post("/api/chat")
async def api_chat(req: ChatRequest):
    """流式 SSE：发消息，返回 agent.run_task 的 yield 流。"""
    message = req.message.strip()
    if not message:
        return {"error": "message 不能为空"}

    def event_generator():
        for event in agent.run_task(message, stream=True):
            # SSE 格式：data: <json>\n\n
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ============= 启动 =============
if __name__ == "__main__":
    import sys
    import io
    # 修复 Windows 终端中文/emoji 编码问题
    if sys.platform == "win32":
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
        except Exception:
            pass

    import uvicorn
    print("=" * 60)
    print("[Agent] Core Agent v0 starting...")
    print("  6 capabilities: Perceive / Think / Remember / Act / Express / Collaborate")
    print("  LLM: MockLLM (keyword pattern matching)")
    print("=" * 60)
    print("\n>> Open browser: http://localhost:8000\n")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")