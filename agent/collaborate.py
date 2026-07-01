"""
协作（Collaborate）· v0 最核心实现

v0 范围：
    ① A2A 调用    - 我能调其他 Agent（agent-to-agent call）
    ② 被调用接口   - 我能作为工具被其他 Agent 调用（agent-as-tool）

不做（→ TODO.md）：
    - MCP（外部工具协议）
    - 多 Agent 编排（Leader/Worker/Verifier）
    - 复杂拓扑（Blackboard）
    - 跨平台 / 跨进程
    - 4 Transport（L1 Local / L2 Cluster / L3 Cross-platform / L4 Cross-vendor）
    - 8 原语（discover / call / subscribe / handoff / cancel / result / heartbeat / vote）
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class AgentCard:
    """Agent 的对外名片（被调用时用）。"""
    name: str
    description: str
    capabilities: list[str]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "capabilities": self.capabilities,
        }


class Collaborate:
    """协作层：管理 sub-agent + 暴露自身为工具。"""

    def __init__(self, self_name: str = "main"):
        self.self_name = self_name
        self.sub_agents: dict[str, "Collaborate"] = {}   # name -> sub-agent
        self.card: AgentCard | None = None               # 自己的名片

    def register_sub_agent(self, name: str, sub_agent: "Collaborate", description: str = "", capabilities: list[str] | None = None) -> None:
        """注册一个 sub-agent（v0 = 本地 dict；未来 = 注册中心）。"""
        self.sub_agents[name] = sub_agent
        sub_agent.card = AgentCard(
            name=name,
            description=description,
            capabilities=capabilities or [],
        )

    def call_agent(self, agent_name: str, task: str) -> dict:
        """v0 子能力 ①：A2A 调用。
        v0 简化版：sub-agent 直接同步执行，返回 dict 结果。
        """
        if agent_name not in self.sub_agents:
            return {"success": False, "error": f"未知 agent: {agent_name}"}
        sub = self.sub_agents[agent_name]
        return sub.handle_call(task=task, caller=self.self_name)

    def handle_call(self, task: str, caller: str) -> dict:
        """v0 子能力 ②：被其他 Agent 调用的入口。
        v0 简化版：作为工具暴露，返回简化结果。
        """
        return {
            "success": True,
            "caller": caller,
            "agent": self.self_name,
            "task": task,
            "result": f"[{self.self_name}] 已接收任务（v0 stub，未实际执行）",
        }

    def as_tool_definition(self) -> dict:
        """把自己包装成 tool 定义，让其他 Agent 能调。"""
        if not self.card:
            return {}
        return {
            "type": "function",
            "function": {
                "name": f"call_agent_{self.card.name}",
                "description": self.card.description or f"调用 {self.card.name} Agent",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "要交给子 Agent 处理的任务",
                        }
                    },
                    "required": ["task"],
                },
            },
        }