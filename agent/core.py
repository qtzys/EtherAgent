"""
Agent 核心 · 主循环

v0 范围：ReAct 循环（感知 → 思考 ⇄ 记忆 → 行动 → 表达），含失败检测。

不做（→ TODO.md）：
    - Plan-and-Execute（多步规划）
    - 反思作为一等公民（reflexion 闭环）
    - Belief State
    - 跨 session 持久化
    - 异步 / 并发 / 多 Agent 协同
"""

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterator

from .act import Act, ActionResult, ToolRegistry
from .audit import AuditLogger
from .collaborate import Collaborate
from .express import Express
from .llm import LLM, MockLLM
from .perceive import Observation, Perceive
from .remember import Remember
from .storage import Storage
from .think import Decision, Think
from .belief import BeliefState, BKey


@dataclass
class StepLog:
    """单步日志（用于回显 + 调试）。"""
    iteration: int
    decision: Decision
    action_result: ActionResult | None = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "iteration": self.iteration,
            "decision": self.decision.to_dict(),
            "action_result": self.action_result.to_dict() if self.action_result else None,
            "timestamp": self.timestamp,
        }


@dataclass
class TaskRecord:
    """任务记录（左栏列表显示用）。"""
    task_id: str
    title: str
    status: str = "进行中"     # 进行中 / 已完成 / 失败
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    finished_at: str | None = None
    steps: list[StepLog] = field(default_factory=list)
    files: list[str] = field(default_factory=list)   # 附件
    final_answer: str = ""

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "status": self.status,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
            "files": self.files,
            "steps": [s.to_dict() for s in self.steps],
            "final_answer": self.final_answer,
        }


class Agent:
    """最核心 Agent v0：6 能力的容器 + 主循环。"""

    def __init__(
        self,
        llm: LLM | None = None,
        tool_registry: ToolRegistry | None = None,
        storage: Storage | None = None,
        audit: AuditLogger | None = None,
    ):
        # 6 能力实例化
        self.perceive = Perceive()
        self.think = Think(llm or MockLLM())
        # 存储（先创建，下面 remember/audit/belief 都用它）
        self.storage = storage or Storage()
        # 记忆接入 storage（v0.2 = 重要性打分 + 持久化）
        self.remember = Remember(
            max_items=50,
            session_id="default",
            storage=self.storage,
        )
        self.tool_registry = tool_registry or ToolRegistry()
        self.act = Act(self.tool_registry)
        self.express = Express()
        self.collaborate = Collaborate(self_name="main")

        # 持久化 + 审计
        self.audit = audit or AuditLogger(self.storage)

        # v0.2 Belief State（最小版：注入 + 校准 + 提示）
        self.belief = BeliefState(storage=self.storage)
        self.belief.sync_tools(self.tool_registry.names())

        # 任务记录（内存缓存；持久化在 storage）
        self.tasks: list[TaskRecord] = []
        self.current_task: TaskRecord | None = None

        # 从存储加载历史任务
        self._load_tasks_from_storage()

        # 注册内置工具（如果已加载）
        try:
            from tools.builtin import register_builtin_tools
            register_builtin_tools(self.tool_registry)
            # 同步工具列表到 belief
            self.belief.sync_tools(self.tool_registry.names())
        except ImportError:
            pass  # 工具模块未加载，跳过

    def _load_tasks_from_storage(self) -> None:
        """启动时从 SQLite 加载历史任务。"""
        try:
            stored = self.storage.list_tasks(limit=200)
            for t in stored:
                rec = TaskRecord(
                    task_id=t["id"],
                    title=t["title"],
                    status=t["status"],
                    created_at=t["created_at"],
                    finished_at=t.get("finished_at"),
                    files=t.get("files", []),
                    final_answer=t.get("final_answer", ""),
                )
                # 还原 steps
                for sd in t.get("steps", []):
                    rec.steps.append(StepLog(
                        iteration=sd.get("iteration", 0),
                        decision=Decision(
                            action=sd["decision"].get("action", "answer"),
                            tool_name=sd["decision"].get("tool_name"),
                            tool_args=sd["decision"].get("tool_args", {}),
                            content=sd["decision"].get("content", ""),
                            reasoning=sd["decision"].get("reasoning", ""),
                            confidence=sd["decision"].get("confidence", 1.0),
                        ),
                        action_result=ActionResult(
                            success=sd["action_result"]["success"],
                            tool_name=sd["action_result"]["tool_name"],
                            result=sd["action_result"].get("result"),
                            error=sd["action_result"].get("error"),
                        ) if sd.get("action_result") else None,
                        timestamp=sd.get("timestamp", ""),
                    ))
                self.tasks.append(rec)
        except Exception as e:
            print(f"[Agent] Load tasks from storage failed: {e}")

    # ============= 主入口 =============
    def run_task(self, user_message: str, stream: bool = True) -> Iterator[dict]:
        """执行一个任务，yield 流式事件。
        事件类型（每条 dict）：
          - {"type": "task_start",   "task_id": ...}
          - {"type": "thinking",     "reasoning": ...}
          - {"type": "tool_call",    "tool": ..., "args": ...}
          - {"type": "tool_result",  "success": ..., "result": ...}
          - {"type": "text_chunk",   "text": "..."}     # 流式文本
          - {"type": "answer",       "content": "..."}
          - {"type": "file",         "path": ...}
          - {"type": "task_end",     "status": "..."}
          - {"type": "fail",         "reason": "..."}
        """
        task_id = uuid.uuid4().hex[:8]
        title = user_message[:30] + ("..." if len(user_message) > 30 else "")
        task = TaskRecord(task_id=task_id, title=title)
        self.tasks.append(task)
        self.current_task = task
        self.remember.clear()

        # 信念：更新当前任务 + 刷新工具列表
        self.belief.set_current_task(title)
        self.belief.sync_tools(self.tool_registry.names())

        # 审计 + 持久化
        self.audit.task_start(task_id=task_id, title=title)
        self._persist_task(task)

        yield {"type": "task_start", "task_id": task_id, "title": title}

        # 1. 感知：接收用户输入
        obs = self.perceive.receive_input(user_message)
        self.remember.encode("user_message", user_message)
        yield {"type": "perceive", "observation": obs.to_dict()}

        # 2. ReAct 主循环：思考 ⇄ 行动
        iteration = 0
        history: list[Decision] = []
        final_answer = ""

        while True:
            iteration += 1

            # 2a. 思考
            available_tools = self.tool_registry.names() + ["call_sub_agent"]
            memory_summary = self.remember.retrieve()
            belief_summary = self.belief.to_prompt()
            # 把信念状态注入到 memory_summary，让 LLM 看到
            memory_summary = f"{belief_summary}\n\n{memory_summary}"
            decision = self.think.decide(
                observation=obs.to_dict(),
                memory_summary=memory_summary,
                available_tools=available_tools,
            )

            yield {"type": "thinking", "reasoning": decision.reasoning, "iteration": iteration}

            step = StepLog(iteration=iteration, decision=decision)
            task.steps.append(step)
            history.append(decision)

            # 2b. 决策分支
            if decision.action == "fail" or self.think.detect_failure(history):
                reason = decision.reasoning or "思考循环失败 / 死循环"
                yield {"type": "fail", "reason": reason}
                task.status = "失败"
                task.finished_at = datetime.now().isoformat()
                self.audit.task_end(task_id=task_id, status="失败", steps=len(task.steps))
                self._persist_task(task)
                yield {"type": "task_end", "task_id": task_id, "status": "失败"}
                return

            if decision.action == "answer":
                # 3. 表达：流式输出
                final_answer = decision.content
                task.final_answer = final_answer
                self.remember.encode("assistant_message", final_answer)

                if stream:
                    buf = ""
                    for chunk in self.express.stream(final_answer, chunk_size=12):
                        buf += chunk
                        yield {"type": "text_chunk", "text": chunk}
                        time.sleep(0.02)   # 模拟流式延迟
                else:
                    yield {"type": "text_chunk", "text": final_answer}

                yield {"type": "answer", "content": final_answer}
                task.status = "已完成"
                task.finished_at = datetime.now().isoformat()
                # 审计 + 持久化
                self.audit.task_end(task_id=task_id, status="已完成", steps=len(task.steps))
                self._persist_task(task)
                yield {"type": "task_end", "task_id": task_id, "status": "已完成"}
                return

            if decision.action == "call_tool":
                # 4. 行动：调工具
                yield {
                    "type": "tool_call",
                    "tool": decision.tool_name,
                    "args": decision.tool_args,
                    "iteration": iteration,
                }
                # 审计：工具调用
                self.audit.tool_call(task_id=task_id, tool=decision.tool_name, args=decision.tool_args)

                if decision.tool_name == "call_sub_agent":
                    # 协作：调 sub-agent
                    result_dict = self.collaborate.call_agent(
                        decision.tool_args.get("agent_name", ""),
                        decision.tool_args.get("task", ""),
                    )
                    result = ActionResult(
                        success=result_dict.get("success", False),
                        tool_name="call_sub_agent",
                        result=result_dict,
                    )
                else:
                    # 普通工具
                    result = self.act.execute(decision.tool_name, decision.tool_args)

                step.action_result = result
                # 审计：工具结果
                self.audit.tool_result(
                    task_id=task_id,
                    tool=result.tool_name,
                    success=result.success,
                    error=result.error,
                )
                yield {"type": "tool_result", **result.to_dict()}

                # 如果工具生成了文件，加入附件列表
                if decision.tool_name == "write_file" and result.success:
                    path = decision.tool_args.get("path", "output.txt")
                    if path not in task.files:
                        task.files.append(path)
                    yield {"type": "file", "path": path}

                # 5. 感知回流：把结果存记忆 + 进入下一轮
                obs = self.perceive.observe_action_result(
                    tool_name=result.tool_name,
                    result=result.result,
                    error=result.error,
                )
                self.remember.encode("tool_result", result.to_dict())
                # 信念校准：根据工具结果更新 confidence
                self.belief.record_tool_outcome(
                    tool_name=result.tool_name,
                    success=result.success,
                )
                # 继续 while 循环

    # ============= 辅助方法 =============
    def list_tasks(self) -> list[dict]:
        return [t.to_dict() for t in self.tasks]

    def get_task(self, task_id: str) -> dict | None:
        for t in self.tasks:
            if t.task_id == task_id:
                return t.to_dict()
        return None

    def delete_task(self, task_id: str) -> bool:
        """删除指定任务。返回是否删除成功。"""
        deleted = False
        for i, t in enumerate(self.tasks):
            if t.task_id == task_id:
                self.tasks.pop(i)
                if self.current_task and self.current_task.task_id == task_id:
                    self.current_task = None
                deleted = True
                break
        if deleted:
            self.storage.delete_task(task_id)
            self.audit.task_delete(task_id=task_id)
        return deleted

    def clear_tasks(self) -> int:
        """清空所有任务。返回删除数量。"""
        n = len(self.tasks)
        self.tasks.clear()
        self.current_task = None
        self.storage.clear_tasks()
        return n

    def _persist_task(self, task: TaskRecord) -> None:
        """把任务存到 SQLite（实时持久化）。"""
        try:
            self.storage.save_task(task.to_dict())
        except Exception as e:
            print(f"[Agent] Persist task failed: {e}")