"""
审计日志 · v0.2

记录所有重要 action 到 SQLite audit_logs 表。
提供查询、清空接口。
"""

from typing import Any

from .storage import Storage


# 审计日志级别
LEVEL_DEBUG = "debug"
LEVEL_INFO = "info"
LEVEL_WARN = "warn"
LEVEL_ERROR = "error"

# 结果类型
RESULT_OK = "ok"
RESULT_FAIL = "fail"
RESULT_BLOCKED = "blocked"


class AuditLogger:
    """审计日志器。封装 Storage.log_audit，提供业务级方法。"""

    # 预定义 action 名（避免拼写错误）
    A_TASK_START    = "task.start"
    A_TASK_END      = "task.end"
    A_TASK_DELETE   = "task.delete"
    A_TOOL_CALL     = "tool.call"
    A_TOOL_RESULT   = "tool.result"
    A_LLM_CALL      = "llm.call"
    A_LLM_CONFIG    = "llm.config"
    A_LLM_TEST      = "llm.test"
    A_BELIEF_SET    = "belief.set"
    A_BELIEF_UPDATE = "belief.update"
    A_MEMORY_SAVE   = "memory.save"
    A_API_REQUEST   = "api.request"

    def __init__(self, storage: Storage, actor: str = "system"):
        self.storage = storage
        self.actor = actor

    def _log(self, action: str, result: str = RESULT_OK, target: str | None = None, metadata: dict | None = None) -> str:
        return self.storage.log_audit(
            action=action,
            actor=self.actor,
            target=target,
            result=result,
            metadata=metadata or {},
        )

    # ---------- 任务 ----------
    def task_start(self, task_id: str, title: str) -> str:
        return self._log(self.A_TASK_START, target=task_id, metadata={"title": title[:100]})

    def task_end(self, task_id: str, status: str, steps: int) -> str:
        return self._log(self.A_TASK_END, target=task_id, metadata={"status": status, "steps": steps})

    def task_delete(self, task_id: str) -> str:
        return self._log(self.A_TASK_DELETE, target=task_id)

    # ---------- 工具 ----------
    def tool_call(self, task_id: str, tool: str, args: dict) -> str:
        return self._log(self.A_TOOL_CALL, target=tool, metadata={"task_id": task_id, "args": args})

    def tool_result(self, task_id: str, tool: str, success: bool, error: str | None = None) -> str:
        return self._log(
            self.A_TOOL_RESULT,
            result=RESULT_OK if success else RESULT_FAIL,
            target=tool,
            metadata={"task_id": task_id, "error": error},
        )

    # ---------- LLM ----------
    def llm_call(self, model: str, task_id: str, action: str, success: bool) -> str:
        return self._log(
            self.A_LLM_CALL,
            result=RESULT_OK if success else RESULT_FAIL,
            target=model,
            metadata={"task_id": task_id, "decision_action": action},
        )

    def llm_config(self, model: str, base_url: str, source: str = "runtime") -> str:
        return self._log(self.A_LLM_CONFIG, target=model, metadata={"base_url": base_url, "source": source})

    def llm_test(self, model: str, success: bool, error: str | None = None) -> str:
        return self._log(
            self.A_LLM_TEST,
            result=RESULT_OK if success else RESULT_FAIL,
            target=model,
            metadata={"error": error},
        )

    # ---------- 信念 ----------
    def belief_set(self, key: str, confidence: float) -> str:
        return self._log(self.A_BELIEF_SET, target=key, metadata={"confidence": confidence})

    def belief_update(self, key: str, old_conf: float, new_conf: float) -> str:
        return self._log(self.A_BELIEF_UPDATE, target=key, metadata={"old": old_conf, "new": new_conf})

    # ---------- 记忆 ----------
    def memory_save(self, memory_id: str, type_: str, importance: float) -> str:
        return self._log(self.A_MEMORY_SAVE, target=memory_id, metadata={"type": type_, "importance": importance})

    # ---------- API ----------
    def api_request(self, endpoint: str, method: str, status_code: int) -> str:
        return self._log(self.A_API_REQUEST, target=endpoint, metadata={"method": method, "status": status_code})

    # ---------- 查询 ----------
    def recent(self, action: str | None = None, limit: int = 100) -> list[dict]:
        return self.storage.list_audit_logs(action=action, limit=limit)

    def stats(self) -> dict:
        return self.storage.stats()