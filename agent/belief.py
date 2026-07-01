"""
信念状态（Belief State）· v0.2 最小版

v0.2 范围：
    ① key-value 信念存储（含 confidence）
    ② 默认自举：self / environment / identity
    ③ 校准：根据证据（成功/失败）调整 confidence
    ④ 证据链：每条信念记录 evidence 来源
    ⑤ 注入 LLM：把相关信念塞进 prompt
    ⑥ 持久化：通过 Storage.beliefs 表

不做（→ TODO.md）：
    - Bayesian 概率推理
    - 信念图（belief graph）/ 反向推理
    - 跨 session 信念联邦
    - 信念冲突检测（KB 消解）
    - 一阶逻辑 / 概率程序
"""

from datetime import datetime
from typing import Any


# 标准信念 key（用于自举）
class BKey:
    """标准信念 key。"""
    SELF_NAME           = "self.name"             # "最核心 Agent v0"
    SELF_VERSION        = "self.version"          # "0.2.0"
    SELF_CAPABILITIES   = "self.capabilities"     # list[str]
    SELF_TOOLS          = "self.tools"            # list[str]
    ENV_CWD             = "env.cwd"               # 工作目录
    ENV_OS              = "env.os"                # 操作系统
    ENV_TIMEZONE        = "env.timezone"          # 时区
    TASK_CURRENT        = "task.current"          # 当前任务标题
    TASK_HISTORY_LEN    = "task.history_length"   # 历史任务数
    SESSION_ID          = "session.id"            # 会话标识


# 默认置信度
DEFAULT_CONFIDENCE = {
    BKey.SELF_NAME:         1.0,    # 自我身份 = 100% 确定
    BKey.SELF_VERSION:      1.0,
    BKey.SELF_CAPABILITIES: 0.9,
    BKey.SELF_TOOLS:        0.95,
    BKey.ENV_CWD:           0.95,
    BKey.ENV_OS:            1.0,
    BKey.ENV_TIMEZONE:      1.0,
    BKey.TASK_CURRENT:      0.7,
    BKey.TASK_HISTORY_LEN:  1.0,
    BKey.SESSION_ID:        1.0,
}


class BeliefState:
    """信念状态：Agent 对自己 / 环境 / 任务的显式认知。

    每条信念 = (key, value, confidence, evidence)
    confidence ∈ [0, 1]；越接近 1 越确定。
    """

    def __init__(self, storage=None):
        self.storage = storage
        self._ensure_bootstrap()

    # ---------- 初始化 ----------
    def _ensure_bootstrap(self) -> None:
        """自举：确保默认信念已注入存储。"""
        if not self.storage:
            return
        for key, conf in DEFAULT_CONFIDENCE.items():
            existing = self.storage.get_belief(key)
            if not existing:
                value, evidence = self._default_value_for(key)
                self.storage.set_belief(
                    key=key,
                    value=value,
                    confidence=conf,
                    evidence=f"[bootstrap] {evidence}",
                )

    def _default_value_for(self, key: str) -> tuple[Any, str]:
        """生成默认 value。"""
        import os
        import platform
        if key == BKey.SELF_NAME:
            return "最核心 Agent v0", "自身标识"
        if key == BKey.SELF_VERSION:
            return "0.2.0", "版本号"
        if key == BKey.SELF_CAPABILITIES:
            return [
                "perceive（感知）",
                "think（思考 - ReAct）",
                "remember（记忆 - 重要性 + 三维检索）",
                "act（行动 - 工具调用）",
                "express（表达 - 流式输出）",
                "collaborate（协作 - A2A）",
            ], "v0.2 激活的 6 项核心能力"
        if key == BKey.SELF_TOOLS:
            return [], "由 ToolRegistry 动态填充"
        if key == BKey.ENV_CWD:
            return os.getcwd(), "运行时检测"
        if key == BKey.ENV_OS:
            return f"{platform.system()} {platform.release()}", "运行时检测"
        if key == BKey.ENV_TIMEZONE:
            try:
                from datetime import timezone
                tz = datetime.now(timezone.utc).astimezone().tzname()
            except Exception:
                tz = "UTC"
            return tz or "UTC", "运行时检测"
        if key == BKey.TASK_CURRENT:
            return "", "无正在进行的任务"
        if key == BKey.TASK_HISTORY_LEN:
            return 0, "启动时为 0"
        if key == BKey.SESSION_ID:
            return "default", "默认 session"
        return "", ""

    # ---------- CRUD ----------
    def set(self, key: str, value: Any, confidence: float = 0.7, evidence: str = "") -> str | None:
        """设置一条信念（覆盖式）。"""
        if not self.storage:
            return None
        # 截断过长的字符串
        if isinstance(value, str) and len(value) > 1000:
            value = value[:1000] + "..."
        self.storage.set_belief(
            key=key,
            value=value,
            confidence=max(0.0, min(1.0, confidence)),
            evidence=evidence[:200],
        )
        return key

    def get(self, key: str) -> dict | None:
        """获取一条信念。返回 dict（含 key/value/confidence/evidence/updated_at）。"""
        if not self.storage:
            return None
        b = self.storage.get_belief(key)
        if not b:
            return None
        # value 是 JSON 字符串时尽量解析
        return b

    def list_all(self) -> list[dict]:  # noqa: A003 -- intentional naming for API
        """列出所有信念（按 updated_at 倒序）。"""
        if not self.storage:
            return []
        return self.storage.list_beliefs()

    def delete(self, key: str) -> bool:
        if not self.storage:
            return False
        return self.storage.delete_belief(key)

    # ---------- v0.2 子能力 ③：校准 ----------
    def update_confidence(self, key: str, delta: float, evidence: str = "") -> bool:
        """根据证据调整 confidence。delta = +0.05 增强，-0.1 削弱。

        校准规则（v0 简化）：
          - 工具成功且结果符合预期 → delta = +0.05
          - 工具失败 / 与预期不符 → delta = -0.15
          - 用户明确纠正 → delta = -0.2
          - 跨 session 一致使用 → delta = +0.02（reinforce）
        """
        if not self.storage:
            return False
        b = self.storage.get_belief(key)
        if not b:
            return False
        old = b["confidence"]
        new = max(0.0, min(1.0, old + delta))
        self.storage.update_belief_confidence(key, new, evidence)
        return True

    # ---------- v0.2 子能力 ⑤：注入 LLM ----------
    def to_prompt(self, max_items: int = 8) -> str:
        """把信念状态格式化成可塞进 LLM prompt 的字符串。

        只取 confidence >= 0.6 的（剔除噪音）+ 高优先的 self/env 优先。
        """
        if not self.storage:
            return "(无信念状态)"

        all_beliefs = self.storage.list_beliefs()
        # 先按 key 优先级排，再按 confidence
        priority_keys = [
            BKey.SELF_NAME, BKey.SELF_VERSION, BKey.SELF_CAPABILITIES,
            BKey.ENV_CWD, BKey.ENV_OS, BKey.TASK_CURRENT,
        ]
        def sort_key(b):
            p = 0 if b["key"] in priority_keys else 1
            return (p, -float(b["confidence"]))

        all_beliefs.sort(key=sort_key)

        lines = []
        n = 0
        for b in all_beliefs:
            if n >= max_items:
                break
            if b["confidence"] < 0.5:
                continue
            # 截短 value
            val = b["value"]
            if isinstance(val, str) and len(val) > 80:
                val = val[:80] + "..."
            lines.append(f"  - {b['key']} = {val} (conf={float(b['confidence']):.2f})")
            n += 1

        if not lines:
            return "(无可用信念)"
        return "我的信念状态（按确定性排序）：\n" + "\n".join(lines)

    # ---------- 工具方法 ----------
    def sync_tools(self, tool_names: list[str]) -> None:
        """同步 self.tools 信念（每次启动 / 注册工具时）。"""
        self.set(
            key=BKey.SELF_TOOLS,
            value=list(tool_names),
            confidence=0.95,
            evidence="ToolRegistry.sync",
        )

    def set_current_task(self, title: str) -> None:
        """更新当前任务信念。"""
        self.set(
            key=BKey.TASK_CURRENT,
            value=title,
            confidence=0.7,
            evidence="task.start",
        )

    def record_tool_outcome(self, tool_name: str, success: bool) -> None:
        """记录工具结果，用于校准。"""
        delta = 0.02 if success else -0.1
        # 如果是 self.tools 下面某个工具成功 → 增强；失败 → 削弱
        existing = self.get(BKey.SELF_TOOLS)
        if existing and tool_name in (existing.get("value") or []):
            self.update_confidence(
                BKey.SELF_TOOLS,
                delta=0.01 if success else -0.02,
                evidence=f"tool={tool_name} success={success}",
            )
        # TASK_CURRENT 校准：根据成功率
        task_b = self.get(BKey.TASK_CURRENT)
        if task_b and task_b.get("value"):
            self.update_confidence(
                BKey.TASK_CURRENT,
                delta=0.05 if success else -0.08,
                evidence=f"tool={tool_name} result",
            )

    def stats(self) -> dict:
        """信念统计。"""
        if not self.storage:
            return {"count": 0, "avg_confidence": 0.0}
        all_b = self.storage.list_beliefs()
        if not all_b:
            return {"count": 0, "avg_confidence": 0.0}
        avg = sum(float(b["confidence"]) for b in all_b) / len(all_b)
        by_conf = {"high>=0.9": 0, "mid>=0.7": 0, "low<0.7": 0}
        for b in all_b:
            c = float(b["confidence"])
            if c >= 0.9:
                by_conf["high>=0.9"] += 1
            elif c >= 0.7:
                by_conf["mid>=0.7"] += 1
            else:
                by_conf["low<0.7"] += 1
        return {
            "count": len(all_b),
            "avg_confidence": round(avg, 3),
            "by_confidence": by_conf,
        }
