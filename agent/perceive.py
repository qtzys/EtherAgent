"""
感知（Perceive）· v0 最核心实现

v0 范围：
    ① 输入接收   - 收 user 文本消息
    ② 行动回流   - 工具调用完把结果拿回来

不做（→ TODO.md）：
    - 多模态（image / audio / file）
    - 环境状态观察（不读 Memory / Belief 快照）
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Observation:
    """感知单元：所有进入 Agent 的信息都包装成 Observation。"""
    type: str                # "user_input" | "action_result" | "system"
    content: Any
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


class Perceive:
    """感知层：把外部信号转化为 Observation。"""

    def receive_input(self, user_message: str) -> Observation:
        """v0 子能力 ①：接收用户输入。"""
        return Observation(
            type="user_input",
            content=user_message,
            metadata={"source": "user"},
        )

    def observe_action_result(self, tool_name: str, result: Any, error: str | None = None) -> Observation:
        """v0 子能力 ②：观察行动结果回流。"""
        return Observation(
            type="action_result",
            content={"tool": tool_name, "result": result, "error": error},
            metadata={"source": "action"},
        )