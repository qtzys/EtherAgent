"""
记忆（Remember）· v0.2 含重要性打分 + 三维检索

v0.2 范围：
    ① 编码         - 把"说了什么 / 做了什么"存下来
    ② 重要性打分   - 根据 type 自动给重要性分
    ③ 三维检索     - 最近性 + 重要性 + 相关性 加权排序
    ④ 跨 session 持久化 - 写入 SQLite
    ⑤ 遗忘         - 超出 Context Window 时滚动丢弃

不做（→ TODO.md）：
    - 反思记忆（reflection as memory）
    - Belief State
    - 多层记忆（L1 Working / L2 Short / L3 Episodic / L4 Semantic / L5 Procedural）
"""

import re
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


# 记忆类型 → 默认重要性（0~1）
DEFAULT_IMPORTANCE = {
    "user_message":     0.6,
    "assistant_message": 0.5,
    "tool_call":        0.4,
    "tool_result":      0.5,
    "tool_failure":     0.8,    # 失败很重要（值得反思）
    "reflection":       0.9,    # 反思最重要
    "belief_update":    0.85,
    "fact":             0.7,    # 显式事实
    "user_preference":  0.75,
}


@dataclass
class MemoryItem:
    """记忆单元。"""
    type: str                # "user_message" | "assistant_message" | "tool_call" | ...
    content: Any
    importance: float = 0.5
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    memory_id: str | None = None   # SQLite 中的 id（持久化后回填）

    def to_text(self) -> str:
        if isinstance(self.content, str):
            return self.content
        return str(self.content)


class Remember:
    """记忆层：当前会话的上下文管理 + 持久化。"""

    def __init__(self, max_items: int = 50, session_id: str | None = None, storage=None):
        self.session_id = session_id or "default"
        self.storage = storage   # 可选：注入 SQLite 存储
        self.items: deque[MemoryItem] = deque(maxlen=max_items)

    # ---------- v0.2 子能力 ①：编码 + 自动重要性 ----------
    def encode(self, type_: str, content: Any, importance: float | None = None) -> None:
        """把一条新信息存入记忆（含自动重要性打分 + 持久化）。"""
        if importance is None:
            importance = DEFAULT_IMPORTANCE.get(type_, 0.5)

        # 内容长度奖励：内容越长越重要（最多 +0.1）
        text = content if isinstance(content, str) else str(content)
        if len(text) > 200:
            importance = min(1.0, importance + 0.1)

        item = MemoryItem(type=type_, content=content, importance=round(importance, 3))
        self.items.append(item)

        # 持久化
        if self.storage:
            try:
                mid = self.storage.save_memory(
                    session_id=self.session_id,
                    type_=type_,
                    content=content,
                    importance=item.importance,
                )
                item.memory_id = mid
            except Exception as e:
                print(f"[Remember] Persist failed: {e}")

    def reinforce(self, item: MemoryItem, delta: float = 0.05) -> None:
        """强化某条记忆的重要性（每次被访问 +delta）。"""
        item.importance = min(1.0, item.importance + delta)
        if item.memory_id and self.storage:
            self.storage.update_memory_importance(item.memory_id, item.importance)

    # ---------- v0.2 子能力 ②：三维检索 ----------
    def retrieve(self, query: str | None = None, top_k: int = 10) -> str:
        """三维加权检索：最近性 × 重要性 × 相关性。
        返回拼接好的字符串（用于塞进 LLM prompt）。
        """
        if not self.items:
            return "(记忆为空)"

        scored = self._score(query, top_k)

        # 输出格式
        lines = []
        for item, score in scored:
            tag = f"[{item.type}] ★{item.importance:.2f}"
            lines.append(f"{tag} {item.to_text()}")
        return "\n".join(lines)

    def _score(self, query: str | None, top_k: int) -> list[tuple[MemoryItem, float]]:
        """给记忆打分（最近性 × 重要性 × 相关性）。"""
        now = datetime.now()
        results = []
        query_words = set(re.findall(r"\w+", query.lower())) if query else set()

        for item in self.items:
            # 最近性：1/(1+天数)，越新越高
            try:
                age = (now - datetime.fromisoformat(item.timestamp)).total_seconds() / 86400
                recency = 1.0 / (1.0 + age)
            except Exception:
                recency = 0.5

            # 相关性：query 关键词命中比例
            if query_words:
                content_words = set(re.findall(r"\w+", item.to_text().lower()))
                overlap = len(query_words & content_words)
                relevance = overlap / max(len(query_words), 1)
            else:
                relevance = 0.5

            # 综合得分（最近 0.3 + 重要 0.5 + 相关 0.2）
            score = (
                recency * 0.3 +
                item.importance * 0.5 +
                relevance * 0.2
            )
            results.append((item, round(score, 4)))

        # 排序 + Top-K
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def get_recent(self, n: int = 5) -> list[MemoryItem]:
        """获取最近 n 条记忆。"""
        return list(self.items)[-n:]

    # ---------- v0 子能力 ③：遗忘 ----------
    def forget(self) -> int:
        """超出 maxlen 时自动遗忘最早条目，返回被遗忘数量。"""
        return 0

    def clear(self) -> None:
        """清空记忆（不删 SQLite 持久化数据）。"""
        self.items.clear()

    def clear_all(self) -> int:
        """清空当前 session 的所有持久化记忆。"""
        self.items.clear()
        if self.storage:
            return self.storage.clear_memories(session_id=self.session_id)
        return 0

    def size(self) -> int:
        return len(self.items)

    def stats(self) -> dict:
        """记忆统计。"""
        if not self.items:
            return {"count": 0, "avg_importance": 0.0, "by_type": {}}
        by_type = {}
        total_imp = 0.0
        for item in self.items:
            by_type[item.type] = by_type.get(item.type, 0) + 1
            total_imp += item.importance
        return {
            "count": len(self.items),
            "avg_importance": round(total_imp / len(self.items), 3),
            "by_type": by_type,
            "session_id": self.session_id,
        }