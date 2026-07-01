"""
SQLite 存储层 · v0.2

提供 4 张表：
  - tasks         任务记录（id, title, status, created_at, finished_at, final_answer, steps_json, files_json）
  - memories      记忆条目（id, type, content, importance, session_id, created_at, accessed_at, access_count）
  - beliefs       信念状态（key, value, confidence, evidence, updated_at）
  - audit_logs    审计日志（id, action, actor, target, result, metadata_json, created_at）

v0 设计原则：
  - 单文件 SQLite（agent.db）
  - 不引入 ORM，直接用 sqlite3 标准库
  - WAL 模式提高并发
  - 关键查询建索引
"""

import json
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator


# 默认数据库路径
DEFAULT_DB_PATH = Path(__file__).parent.parent / "agent.db"


class Storage:
    """SQLite 存储封装。所有方法线程安全。"""

    SCHEMA_SQL = """
    -- 任务表
    CREATE TABLE IF NOT EXISTS tasks (
        id           TEXT PRIMARY KEY,
        title        TEXT NOT NULL,
        status       TEXT NOT NULL DEFAULT '进行中',
        created_at   TEXT NOT NULL,
        finished_at  TEXT,
        final_answer TEXT,
        steps_json   TEXT,
        files_json   TEXT
    );

    -- 记忆表
    CREATE TABLE IF NOT EXISTS memories (
        id           TEXT PRIMARY KEY,
        session_id   TEXT NOT NULL,
        type         TEXT NOT NULL,
        content      TEXT NOT NULL,
        importance   REAL NOT NULL DEFAULT 0.5,
        created_at   TEXT NOT NULL,
        accessed_at  TEXT NOT NULL,
        access_count INTEGER NOT NULL DEFAULT 0
    );

    -- 信念表
    CREATE TABLE IF NOT EXISTS beliefs (
        key         TEXT PRIMARY KEY,
        value       TEXT NOT NULL,
        confidence  REAL NOT NULL DEFAULT 0.5,
        evidence    TEXT,
        updated_at  TEXT NOT NULL
    );

    -- 审计日志表
    CREATE TABLE IF NOT EXISTS audit_logs (
        id            TEXT PRIMARY KEY,
        action        TEXT NOT NULL,
        actor         TEXT NOT NULL,
        target        TEXT,
        result        TEXT NOT NULL,
        metadata_json TEXT,
        created_at    TEXT NOT NULL
    );

    -- 索引
    CREATE INDEX IF NOT EXISTS idx_memories_session   ON memories(session_id);
    CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance DESC);
    CREATE INDEX IF NOT EXISTS idx_audit_action       ON audit_logs(action);
    CREATE INDEX IF NOT EXISTS idx_audit_created      ON audit_logs(created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_tasks_created      ON tasks(created_at DESC);
    """

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        """初始化数据库（创建表 + 索引）。"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.executescript(self.SCHEMA_SQL)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.commit()

    # ============= 通用 =============
    def _new_id(self) -> str:
        return uuid.uuid4().hex[:12]

    def _now(self) -> str:
        return datetime.now().isoformat()

    # ============= 任务 =============
    def save_task(self, task: dict) -> None:
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO tasks
                   (id, title, status, created_at, finished_at, final_answer, steps_json, files_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    task["task_id"],
                    task["title"],
                    task["status"],
                    task["created_at"],
                    task.get("finished_at"),
                    task.get("final_answer", ""),
                    json.dumps(task.get("steps", []), ensure_ascii=False),
                    json.dumps(task.get("files", []), ensure_ascii=False),
                ),
            )
            conn.commit()

    def get_task(self, task_id: str) -> dict | None:
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if not row:
                return None
            d = dict(row)
            d["steps"] = json.loads(d.pop("steps_json") or "[]")
            d["files"] = json.loads(d.pop("files_json") or "[]")
            return d

    def list_tasks(self, limit: int = 100) -> list[dict]:
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["steps"] = json.loads(d.pop("steps_json") or "[]")
                d["files"] = json.loads(d.pop("files_json") or "[]")
                result.append(d)
            return result

    def delete_task(self, task_id: str) -> bool:
        with self._lock, sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()
            return cur.rowcount > 0

    def clear_tasks(self) -> int:
        with self._lock, sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("DELETE FROM tasks")
            conn.commit()
            return cur.rowcount

    # ============= 记忆 =============
    def save_memory(self, session_id: str, type_: str, content: Any, importance: float = 0.5) -> str:
        """存一条记忆，返回 id。"""
        mid = self._new_id()
        now = self._now()
        content_str = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO memories (id, session_id, type, content, importance, created_at, accessed_at, access_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 0)""",
                (mid, session_id, type_, content_str, importance, now, now),
            )
            conn.commit()
        return mid

    def update_memory_importance(self, memory_id: str, importance: float) -> None:
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE memories SET importance = ? WHERE id = ?",
                (importance, memory_id),
            )
            conn.commit()

    def retrieve_memories(
        self,
        session_id: str,
        query: str | None = None,
        top_k: int = 20,
        recency_weight: float = 0.3,
        importance_weight: float = 0.4,
        relevance_weight: float = 0.3,
    ) -> list[dict]:
        """检索记忆（v1 用三维加权：最近性 + 重要性 + 相关性）。
        v0 简化版：直接按 importance + recency 排序。
        """
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT * FROM memories WHERE session_id = ?
                   ORDER BY importance DESC, created_at DESC LIMIT ?""",
                (session_id, top_k),
            ).fetchall()

            results = []
            now = datetime.now()
            for r in rows:
                d = dict(r)
                # 简易相关性：query 关键词命中数
                relevance = 0.0
                if query:
                    q_words = set(query.lower().split())
                    c_words = set(d["content"].lower().split())
                    overlap = len(q_words & c_words)
                    relevance = overlap / max(len(q_words), 1)
                # 最近性：1 / (1 + 距今天数)
                try:
                    age = (now - datetime.fromisoformat(d["created_at"])).total_seconds() / 86400
                    recency = 1.0 / (1.0 + age)
                except Exception:
                    recency = 0.5

                # 三维加权得分
                score = (
                    d["importance"] * importance_weight +
                    recency * recency_weight +
                    relevance * relevance_weight
                )
                d["score"] = round(score, 4)
                results.append(d)

            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:top_k]

    def list_memories(self, session_id: str, limit: int = 50) -> list[dict]:
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM memories WHERE session_id = ? ORDER BY created_at DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def clear_memories(self, session_id: str | None = None) -> int:
        with self._lock, sqlite3.connect(self.db_path) as conn:
            if session_id:
                cur = conn.execute("DELETE FROM memories WHERE session_id = ?", (session_id,))
            else:
                cur = conn.execute("DELETE FROM memories")
            conn.commit()
            return cur.rowcount

    # ============= 信念 =============
    def set_belief(self, key: str, value: Any, confidence: float = 0.5, evidence: str = "") -> None:
        val_str = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO beliefs (key, value, confidence, evidence, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (key, val_str, confidence, evidence, self._now()),
            )
            conn.commit()

    def get_belief(self, key: str) -> dict | None:
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM beliefs WHERE key = ?", (key,)).fetchone()
            return dict(row) if row else None

    def list_beliefs(self) -> list[dict]:
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute("SELECT * FROM beliefs ORDER BY updated_at DESC").fetchall()]

    def update_belief_confidence(self, key: str, new_confidence: float, evidence: str = "") -> None:
        """校准信念（confidence 修正）。"""
        b = self.get_belief(key)
        if not b:
            return
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """UPDATE beliefs SET confidence = ?, evidence = ?, updated_at = ?
                   WHERE key = ?""",
                (new_confidence, evidence or b["evidence"], self._now(), key),
            )
            conn.commit()

    def delete_belief(self, key: str) -> bool:
        with self._lock, sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("DELETE FROM beliefs WHERE key = ?", (key,))
            conn.commit()
            return cur.rowcount > 0

    # ============= 审计日志 =============
    def log_audit(
        self,
        action: str,
        actor: str,
        result: str = "ok",
        target: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        """记一条审计日志。"""
        log_id = self._new_id()
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO audit_logs (id, action, actor, target, result, metadata_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    log_id,
                    action,
                    actor,
                    target,
                    result,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    self._now(),
                ),
            )
            conn.commit()
        return log_id

    def list_audit_logs(self, action: str | None = None, limit: int = 100) -> list[dict]:
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if action:
                rows = conn.execute(
                    "SELECT * FROM audit_logs WHERE action = ? ORDER BY created_at DESC LIMIT ?",
                    (action, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                if d.get("metadata_json"):
                    try:
                        d["metadata"] = json.loads(d.pop("metadata_json"))
                    except Exception:
                        d["metadata"] = {}
                result.append(d)
            return result

    def clear_audit_logs(self) -> int:
        with self._lock, sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("DELETE FROM audit_logs")
            conn.commit()
            return cur.rowcount

    # ============= 统计 =============
    def stats(self) -> dict:
        """全局统计。"""
        with self._lock, sqlite3.connect(self.db_path) as conn:
            return {
                "tasks":     conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0],
                "memories":  conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0],
                "beliefs":   conn.execute("SELECT COUNT(*) FROM beliefs").fetchone()[0],
                "audit_logs": conn.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0],
                "db_path":   str(self.db_path),
            }

    def reset_all(self) -> None:
        """危险：清空所有表（仅用于测试）。"""
        with self._lock, sqlite3.connect(self.db_path) as conn:
            for table in ("tasks", "memories", "beliefs", "audit_logs"):
                conn.execute(f"DELETE FROM {table}")
            conn.commit()