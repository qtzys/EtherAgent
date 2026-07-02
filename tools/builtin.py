"""
内置工具（v0.2）· 5 个基础工具 + 1 个 sub-agent 包装

工具列表：
    search_web      - 真实网络搜索（Bing HTML，无 key；fallback 到 mock）
    read_file       - 读文件
    write_file      - 写文件
    run_command     - 执行 shell 命令（v0 只支持 ls / pwd / echo 等只读命令）
    save_memory     - 把信息显式存入记忆（跨工具共享）
"""

import datetime
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from agent.act import ToolRegistry


def _real_bing_search(query: str, max_results: int = 5, timeout: float = 8.0) -> dict:
    """真实搜索：调用 cn.bing.com HTML 端点并解析。

    优点：完全免费、不需要任何 API key。
    缺点：Bing 改版可能 break；频率过高会被临时 captcha。
    """
    try:
        import httpx
        from bs4 import BeautifulSoup
    except ImportError:
        return {"error": "需要 httpx + beautifulsoup4: pip install httpx beautifulsoup4", "fallback": True}

    url = "https://cn.bing.com/search"
    params = {"q": query}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            r = client.get(url, params=params, headers=headers)
            r.raise_for_status()
            html = r.text
    except Exception as e:
        return {"error": f"bing request failed: {type(e).__name__}: {e}", "fallback": True}

    soup = BeautifulSoup(html, "html.parser")
    items = soup.find_all("li", class_="b_algo")
    if not items:
        # Bing sometimes uses different class names (e.g. b_result)
        items = soup.find_all("li", class_=re.compile(r"\bb_result\b"))

    results = []
    for li in items[:max_results]:
        title_tag = li.find("h2")
        link_tag = title_tag.find("a") if title_tag else None
        title = link_tag.get_text(strip=True) if link_tag else ""
        href = link_tag.get("href", "") if link_tag else ""

        # 摘要可能在 <p> 里，也可能被分成多个 span
        snippet = ""
        p_tag = li.find("p")
        if p_tag:
            snippet = p_tag.get_text(strip=True)
        if not snippet:
            # 兜底：找带 b_lineclamp 类的元素
            snip_tag = li.find(class_=re.compile(r"b_(paractl|lineclamp|algoSlug)"))
            if snip_tag:
                snippet = snip_tag.get_text(strip=True)

        if title and href:
            results.append({
                "title": title[:200],
                "url": href[:500],
                "snippet": snippet[:300],
            })

    if not results:
        return {"error": "no results parsed", "html_len": len(html), "fallback": True}

    return {
        "query": query,
        "results": results,
        "source": "bing.com (cn.bing.com)",
        "mock": False,
    }


def register_builtin_tools(registry: ToolRegistry) -> None:
    """注册所有内置工具。"""

    # ---------- 1. 真实搜索（Bing + mock fallback） ----------
    def search_web(query: str, max_results: int = 5) -> dict:
        """真实网络搜索（Bing HTML）+ mock 兜底。

        参数：
            query: 搜索关键词
            max_results: 最多返回几条（默认 5）
        返回：
            {
              "query": ...,
              "results": [{"title": ..., "url": ..., "snippet": ...}, ...],
              "source": "bing.com (cn.bing.com)",
              "mock": False/True,
            }
        """
        # 先试真实搜索
        real = _real_bing_search(query, max_results=max_results)
        if real.get("results"):
            return real

        # 失败 / 无结果 → fallback 到 mock，并附上原因
        return {
            "query": query,
            "results": [
                {
                    "title": f"关于 '{query}' 的模拟结果 1",
                    "url": "https://example.com/1",
                    "snippet": f"这是关于 {query} 的第一条搜索结果（Mock — 真实搜索失败：{real.get('error', '未知')})",
                },
                {
                    "title": f"关于 '{query}' 的模拟结果 2",
                    "url": "https://example.com/2",
                    "snippet": f"这是关于 {query} 的第二条搜索结果（Mock）。",
                },
            ],
            "source": "mock (fallback)",
            "mock": True,
            "fallback_reason": real.get("error"),
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
        return {"key": key, "value": value, "saved_at": datetime.datetime.now().isoformat()}

    # 注册到 registry
    registry.register(
        "search_web",
        search_web,
        "搜索网络（Bing HTML 真实搜索；失败 fallback 到 mock）",
    )
    registry.register("read_file",     read_file,     "读取本地文件")
    registry.register("write_file",    write_file,    "写入本地文件")
    registry.register("run_command",   run_command,   "执行 shell 命令（v0 仅限只读）")
    registry.register("save_memory",   save_memory,   "把信息存入长期记忆（v0 stub）")