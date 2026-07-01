"""
内置工具（v0）· 5 个基础工具 + 1 个 sub-agent 包装

工具列表：
    search_web      - 模拟搜索（v0 返回 mock 数据）
    read_file       - 读文件
    write_file      - 写文件
    run_command     - 执行 shell 命令（v0 只支持 ls / pwd / echo 等只读命令）
    save_memory     - 把信息显式存入记忆（跨工具共享）
"""

import datetime
import os
import subprocess
from pathlib import Path

from agent.act import ToolRegistry


def register_builtin_tools(registry: ToolRegistry) -> None:
    """注册所有内置工具。"""

    # ---------- 1. 模拟搜索 ----------
    def search_web(query: str) -> dict:
        """v0 mock：基于 query 关键词返回假数据。真接入要换成 API。"""
        return {
            "query": query,
            "results": [
                {
                    "title": f"关于 '{query}' 的模拟结果 1",
                    "url": "https://example.com/1",
                    "snippet": f"这是关于 {query} 的第一条搜索结果（Mock）。",
                },
                {
                    "title": f"关于 '{query}' 的模拟结果 2",
                    "url": "https://example.com/2",
                    "snippet": f"这是关于 {query} 的第二条搜索结果（Mock）。",
                },
            ],
            "mock": True,
        }

    # ---------- 2. 读文件 ----------
    def read_file(path: str) -> dict:
        try:
            p = Path(path).expanduser().resolve()
            if not p.exists():
                return {"error": f"文件不存在: {path}", "path": path}
            content = p.read_text(encoding="utf-8")
            return {"path": path, "content": content[:2000], "truncated": len(content) > 2000}
        except Exception as e:
            return {"error": str(e), "path": path}

    # ---------- 3. 写文件 ----------
    def write_file(path: str, content: str) -> dict:
        try:
            p = Path(path).expanduser().resolve()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return {"path": path, "size": len(content), "status": "ok"}
        except Exception as e:
            return {"error": str(e), "path": path}

    # ---------- 4. 执行命令（v0 只读模式） ----------
    SAFE_COMMANDS = {"ls", "dir", "pwd", "echo", "cat", "whoami", "date"}

    def run_command(command: str) -> dict:
        cmd = command.strip().split()[0] if command.strip() else ""
        if cmd not in SAFE_COMMANDS:
            return {
                "error": f"v0 沙箱只允许只读命令: {sorted(SAFE_COMMANDS)}",
                "command": command,
                "blocked": True,
            }
        try:
            out = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=10
            )
            return {
                "command": command,
                "stdout": out.stdout[:2000],
                "stderr": out.stderr[:1000],
                "returncode": out.returncode,
            }
        except Exception as e:
            return {"error": str(e), "command": command}

    # ---------- 5. 存记忆（demo 用） ----------
    def save_memory(key: str, value: str) -> dict:
        # v0 只返回确认，不做实际存储
        return {"key": key, "value": value, "saved_at": datetime.datetime.now().isoformat()}

    # 注册到 registry
    registry.register("search_web",    search_web,    "搜索网络（v0 mock，返回模拟数据）")
    registry.register("read_file",     read_file,     "读取本地文件")
    registry.register("write_file",    write_file,    "写入本地文件")
    registry.register("run_command",   run_command,   "执行 shell 命令（v0 仅限只读）")
    registry.register("save_memory",   save_memory,   "把信息存入长期记忆（v0 stub）")