"""
思考（Think）· v0 最核心实现

v0 范围：
    ① 单步推理   - ReAct：看到 observation → 决定下一步
    ② 失败检测   - 检测死循环 / 不收敛，及时叫停

不做（→ TODO.md）：
    - 多模型集成（Ensemble）
    - Plan-and-Execute 多步规划
    - 深度反思
    - Belief State 校准
    - DFS / 搜索式规划
"""

from dataclasses import dataclass, field
from typing import Any, Literal

from .llm import LLM


@dataclass
class Decision:
    """思考的输出：决定下一步做什么。"""
    action: Literal["call_tool", "answer", "fail"]
    tool_name: str | None = None
    tool_args: dict = field(default_factory=dict)
    content: str = ""             # 当 action="answer" 时是给用户的回答
    reasoning: str = ""           # 思考过程（用于回显）
    confidence: float = 1.0       # 0~1，用于后续校准

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "tool_name": self.tool_name,
            "tool_args": self.tool_args,
            "content": self.content,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
        }


class Think:
    """思考层：基于观察 + 记忆 + LLM 做决策。"""

    def __init__(self, llm: LLM, max_iterations: int = 8):
        self.llm = llm
        self.max_iterations = max_iterations

    def decide(self, observation: dict, memory_summary: str, available_tools: list[str]) -> Decision:
        """v0 子能力 ①：单步推理。
        输入：observation + memory 摘要 + 可用工具列表
        输出：Decision（call_tool / answer / fail）
        """
        return self.llm.decide(
            observation=observation,
            memory_summary=memory_summary,
            available_tools=available_tools,
        )

    def detect_failure(self, history: list[Decision]) -> bool:
        """v0 子能力 ②：失败检测。
        简单规则：
          - 超过 max_iterations → 失败
          - 最近 3 步完全相同（同一工具、同一参数） → 死循环
        """
        if len(history) >= self.max_iterations:
            return True

        if len(history) >= 3:
            last3 = history[-3:]
            sig = lambda d: (d.action, d.tool_name, str(sorted(d.tool_args.items())))
            if sig(last3[0]) == sig(last3[1]) == sig(last3[2]):
                return True

        return False