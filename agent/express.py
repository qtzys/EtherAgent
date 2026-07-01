"""
表达（Express）· v0 最核心实现

v0 范围：
    ① 流式输出   - 一个字一个字地吐（chunked）
    ② 结构化结果 - 关键结果用 Markdown / JSON

不做（→ TODO.md）：
    - 多模态输出（image / audio / file 生成）
    - 引用 / cite
    - 按 channel 自适应格式（不同平台不同格式）
    - 偏好驱动的输出风格（简洁 / 详细 / 正式）
"""

from typing import Iterator


class Express:
    """表达层：把内部结果转化为用户可消费的输出。"""

    def stream(self, text: str, chunk_size: int = 8) -> Iterator[str]:
        """v0 子能力 ①：流式输出。
        为了演示流式效果，按 chunk_size 个字符切分。
        真接入 LLM 时这里会是 LLM 的 streaming API。
        """
        if not text:
            return
        for i in range(0, len(text), chunk_size):
            yield text[i : i + chunk_size]

    def structure_markdown(self, content: str) -> str:
        """v0 子能力 ②：返回 Markdown 格式（v0 = 直接返回）。"""
        return content

    def structure_json(self, data: dict) -> str:
        """v0 子能力 ②：结构化 JSON 输出。"""
        import json
        return json.dumps(data, ensure_ascii=False, indent=2)