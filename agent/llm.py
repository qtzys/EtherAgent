"""
LLM 接口 + Mock 实现

v0 默认用 MockLLM（基于模式匹配，无需 API key 即可运行）。
要换成真 LLM，只需实现 LLM 接口即可（参考 RealLLMSkeleton）。

注意：Decision 类型在 think.py 定义。本模块用延迟导入避免循环依赖。
"""

import os
import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .think import Decision


class LLM(ABC):
    """LLM 接口：所有 LLM 实现都要实现 decide() + 可选 stream()。"""

    @abstractmethod
    def decide(self, observation: dict, memory_summary: str, available_tools: list[str]) -> "Decision":
        """看到 observation + memory，做决策。"""
        raise NotImplementedError

    def stream(self, text: str):
        """流式输出（v0 默认走 Mock；真 LLM 可覆盖为 token 级别）。"""
        for i in range(0, len(text), 8):
            yield text[i : i + 8]


class MockLLM(LLM):
    """Mock LLM：基于关键词模式匹配做决策。
    目的：让 v0 Agent 不依赖外部 API 即可运行。
    """

    # 工具触发模式（中文）
    TOOL_PATTERNS = [
        ("search_web",      [r"搜索", r"查一下", r"在网上", r"上网", r"搜一下", r"查询"]),
        ("read_file",       [r"读取", r"打开", r"看看文件", r"看.*\.md", r"看.*\.txt", r"看.*\.py"]),
        ("write_file",      [r"写文件", r"创建文件", r"保存", r"生成.*文件", r"写到"]),
        ("run_command",     [r"执行", r"运行", r"跑一下", r"ls\b", r"dir\b", r"pwd"]),
        ("call_sub_agent",  [r"让.*做", r"交给.*", r"调用.*agent", r"派给"]),
    ]

    def decide(self, observation, memory_summary, available_tools):
        # 延迟导入避免循环
        from .think import Decision

        obs_type = observation.get("type")
        content = str(observation.get("content", ""))

        # 如果是行动结果回流 → 通常走向 answer
        if obs_type == "action_result":
            return self._decide_after_action(content)

        # 用户输入 → 匹配工具模式
        for tool_name, patterns in self.TOOL_PATTERNS:
            for pat in patterns:
                if re.search(pat, content):
                    args = self._extract_args(tool_name, content)
                    if tool_name in available_tools or tool_name == "call_sub_agent":
                        return Decision(
                            action="call_tool",
                            tool_name=tool_name,
                            tool_args=args,
                            reasoning=f"检测到'{tool_name}'触发词：{pat}",
                            confidence=0.7,
                        )

        # 默认：直接给用户回答
        return self._generate_answer(content, memory_summary)

    def _decide_after_action(self, action_result_str):
        from .think import Decision
        return Decision(
            action="answer",
            content=self._format_action_result(action_result_str),
            reasoning="已获取工具结果，整合后回复用户",
            confidence=0.85,
        )

    def _generate_answer(self, user_msg, memory):
        from .think import Decision
        if any(kw in user_msg for kw in ["你好", "hi", "hello", "嗨"]):
            reply = "你好！我是最核心 Agent，已激活 6 项核心能力：感知/思考/记忆/行动/表达/协作。有什么可以帮你的？"
        elif any(kw in user_msg for kw in ["你是谁", "介绍", "你能做什么"]):
            reply = (
                "我是 v0 最核心 Agent：\n"
                "• 🟢 感知 - 接收输入\n"
                "• 🔵 思考 - ReAct 推理 + 失败检测\n"
                "• 🟡 记忆 - 单会话上下文\n"
                "• 🟠 行动 - 工具调用\n"
                "• 🟣 表达 - 流式输出\n"
                "• 🔴 协作 - A2A 调用 / 被调用\n\n"
                "完整能力清单见 TODO.md"
            )
        elif any(kw in user_msg for kw in ["todo", "TODO", "待办", "没做"]):
            reply = "TODO.md 列出了 v0 没做的所有能力。打开 核心Agent/TODO.md 看详细清单。"
        else:
            preview = user_msg[:60] + ("..." if len(user_msg) > 60 else "")
            reply = (
                f"收到：{preview}\n\n"
                f"（Mock 模式 - 关键词未匹配到工具触发器）\n"
                f"建议尝试：搜索/读取/写文件/执行 等动词开头的指令。\n"
                f"或者输入 'todo' 查看待办清单。"
            )
        return Decision(action="answer", content=reply, reasoning="直接回答用户", confidence=0.6)

    def _format_action_result(self, result_str):
        return f"工具执行完成。结果已记录。\n\n{result_str[:500]}"

    def _extract_args(self, tool_name, content):
        if tool_name == "search_web":
            q = re.sub(r"(搜索|查一下|在网上|上网|搜一下|查询)", "", content).strip()
            return {"query": q or content}
        if tool_name == "read_file":
            m = re.search(r"[\w./\\-]+\.(md|txt|py|json|yaml|yml)", content)
            return {"path": m.group(0) if m else content}
        if tool_name == "write_file":
            return {"path": "output.txt", "content": content}
        if tool_name == "run_command":
            return {"command": content.strip()}
        if tool_name == "call_sub_agent":
            return {"agent_name": "researcher", "task": content}
        return {}


class RealLLMSkeleton(LLM):
    """真 LLM 的骨架实现（未完成 — TODO 接入 Claude / OpenAI）。"""

    def __init__(self, api_key="", model="claude-sonnet-4-6"):
        self.api_key = api_key
        self.model = model

    def decide(self, observation, memory_summary, available_tools):
        # TODO: 接入真实 LLM API
        raise NotImplementedError("TODO: 接入真 LLM API（Claude / OpenAI / 其他）")


class RealLLM(LLM):
    """真实 LLM 接入（基于 anthropic SDK）。

    支持：
      - Anthropic Messages API（含 streaming + tool_use）
      - 通过环境变量配置 base_url（兼容 MiniMax 等代理）
      - 通过 set_api_key() 在运行时切换 key（前端输入用）
      - 流式输出
    """

    # ---------- 默认配置 ----------
    DEFAULT_MODEL = "claude-sonnet-4-6"
    DEFAULT_BASE_URL = None   # None = 用 anthropic 官方
    DEFAULT_MAX_TOKENS = 4096

    # ---------- 决策 Prompt 模板 ----------
    SYSTEM_PROMPT = """你是 Agent 的"决策脑"，负责根据当前观察和记忆，决定下一步该做什么。

你的输出必须是严格的 JSON，格式如下：
{
  "action": "call_tool" | "answer" | "fail",
  "tool_name": "工具名"或 null,
  "tool_args": {参数} 或 {},
  "content": "给用户的回答"或 "",
  "reasoning": "你为什么这样决策",
  "confidence": 0.0~1.0
}

规则：
1. 如果用户消息触发了某个工具（如"搜索 xxx" → search_web），返回 action=call_tool
2. 如果可以基于已有信息直接回答，返回 action=answer
3. 如果遇到无法继续的情况（信息不足、矛盾等），返回 action=fail
4. reasoning 要简洁但说明关键判断依据
5. confidence 是你对这个决策的把握（用于后续校准）
6. content 在 action=answer 时必填，且要直接回答用户
"""

    USER_PROMPT_TEMPLATE = """当前观察：
{observation}

记忆摘要（最近 20 条）：
{memory_summary}

可用工具：
{available_tools}

请基于以上信息做出决策（必须是严格 JSON）。"""

    def __init__(self, api_key: str | None = None, model: str | None = None,
                 base_url: str | None = None, max_tokens: int | None = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.model = model or os.getenv("LLM_MODEL", self.DEFAULT_MODEL)
        self.base_url = base_url or os.getenv("ANTHROPIC_BASE_URL", self.DEFAULT_BASE_URL)
        self.max_tokens = max_tokens or int(os.getenv("LLM_MAX_TOKENS", self.DEFAULT_MAX_TOKENS))
        self._client = None

    def set_api_key(self, api_key: str, base_url: str | None = None, model: str | None = None) -> None:
        """运行时更新 key（前端输入用）。"""
        self.api_key = api_key
        if base_url is not None:
            self.base_url = base_url
        if model is not None:
            self.model = model
        self._client = None   # 强制重建 client

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
            except ImportError:
                raise ImportError("请先安装 anthropic SDK: pip install anthropic")
            kwargs = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = anthropic.Anthropic(**kwargs)
        return self._client

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def decide(self, observation, memory_summary, available_tools):
        """调真 LLM 做决策。"""
        from .think import Decision

        if not self.is_configured():
            raise ValueError("API key 未配置。请设置 ANTHROPIC_API_KEY 环境变量，或在前端输入。")

        client = self._get_client()

        user_msg = self.USER_PROMPT_TEMPLATE.format(
            observation=observation,
            memory_summary=memory_summary or "(空)",
            available_tools=", ".join(available_tools) or "(无)",
        )

        try:
            message = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=self.SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
            )
        except Exception as e:
            # 网络错误 / 鉴权失败 → 返回 fail
            return Decision(
                action="fail",
                reasoning=f"LLM 调用失败: {type(e).__name__}: {e}",
                confidence=0.0,
            )

        # 解析返回：可能含 thinking + text
        text_content = ""
        for block in message.content:
            if block.type == "text":
                text_content += block.text

        # 从 text 中提取 JSON
        decision = self._parse_decision(text_content)
        decision.reasoning = (
            f"[{self.model}] {decision.reasoning or '无 reasoning'}"
        )
        return decision

    def _parse_decision(self, text: str) -> "Decision":
        """从 LLM 输出文本中解析 Decision JSON。"""
        from .think import Decision
        import json

        # 尝试提取 ```json ... ``` 代码块
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if m:
            json_str = m.group(1)
        else:
            # 尝试直接找 {...}
            m = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
            if m:
                json_str = m.group(0)
            else:
                # 兜底：当作 answer
                return Decision(
                    action="answer",
                    content=text.strip(),
                    reasoning="LLM 输出非 JSON，当作纯回答处理",
                    confidence=0.5,
                )

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            return Decision(
                action="answer",
                content=text.strip(),
                reasoning=f"JSON 解析失败: {e}",
                confidence=0.3,
            )

        # 构造 Decision
        action = data.get("action", "answer")
        if action not in ("call_tool", "answer", "fail"):
            action = "answer"

        return Decision(
            action=action,
            tool_name=data.get("tool_name"),
            tool_args=data.get("tool_args", {}) or {},
            content=data.get("content", ""),
            reasoning=data.get("reasoning", ""),
            confidence=float(data.get("confidence", 0.7)),
        )

    def stream(self, text: str):
        """流式输出（v0 简单按字符切；真 LLM 时上层会用 LLM 的 streaming 替代）。"""
        for i in range(0, len(text), 8):
            yield text[i : i + 8]