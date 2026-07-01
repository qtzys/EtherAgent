"""
行动（Act）· v0 最核心实现

v0 范围：
    ① 工具调用   - 通过 tool registry 调外部工具
    ② 失败回滚   - 工具调用失败时不阻塞主循环

不做（→ TODO.md）：
    - Side Effect Tracking（before/after 对比）
    - 细粒度权限控制（auto / ask / deny 三态）
    - 高风险行动强制 HITL
    - 沙箱执行（Docker / SSH / OpenShell）
    - Toolset 系统（工具分类管理）
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable


@dataclass
class ActionResult:
    """行动结果。"""
    success: bool
    tool_name: str
    result: Any = None
    error: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "tool_name": self.tool_name,
            "result": self.result,
            "error": self.error,
            "timestamp": self.timestamp,
        }


class ToolRegistry:
    """工具注册中心。"""

    def __init__(self):
        self._tools: dict[str, Callable] = {}

    def register(self, name: str, func: Callable, description: str = "") -> None:
        self._tools[name] = {"func": func, "description": description}

    def list_tools(self) -> list[dict]:
        return [
            {"name": name, "description": info["description"]}
            for name, info in self._tools.items()
        ]

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def call(self, name: str, **kwargs) -> Any:
        if name not in self._tools:
            raise ValueError(f"未知工具: {name}")
        return self._tools[name]["func"](**kwargs)


class Act:
    """行动层：执行工具调用，含失败回滚（v0 = 不阻塞）。"""

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def execute(self, tool_name: str, tool_args: dict) -> ActionResult:
        """v0 子能力 ①+②：执行工具调用，失败时返回错误而不抛异常。"""
        try:
            result = self.registry.call(tool_name, **tool_args)
            return ActionResult(success=True, tool_name=tool_name, result=result)
        except Exception as e:
            # v0 失败回滚：返回错误结果，主循环决定下一步
            return ActionResult(
                success=False,
                tool_name=tool_name,
                error=f"{type(e).__name__}: {str(e)}",
            )