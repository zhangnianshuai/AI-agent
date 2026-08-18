"""
系统级工具 — 文件读写 / 目录浏览 / 日志查看

仅供 SQL Agent（admin）使用，操作范围限定在 store/agent/ 目录内，防止路径穿越。
"""

import json
import os
from pathlib import Path

from langchain_core.tools import tool

# 所有文件操作限定在此根目录内
_STORE_ROOT = Path(__file__).resolve().parent.parent.parent / "store" / "agent"
os.makedirs(_STORE_ROOT, exist_ok=True)

_MAX_READ_BYTES = 64 * 1024  # 单次读取上限 64KB


def _safe_path(rel_path: str) -> Path:
    """将相对路径解析为 store 内的绝对路径，防止路径穿越"""
    p = (_STORE_ROOT / rel_path).resolve()
    if not str(p).startswith(str(_STORE_ROOT.resolve())):
        raise ValueError(f"路径越界: {rel_path}")
    return p


# ── 文件工具 ──────────────────────────────────────────────

@tool
def read_file(path: str, max_chars: int = 4096) -> str:
    """读取 store/agent/ 下指定文件的内容（仅限文本文件）。

    Args:
        path: store 目录下的相对路径，如 "user_resume/123.pdf"（PDF 不可读）
        max_chars: 最大返回字符数，默认 4096

    Returns:
        {"ok": true, "content": "...", "size": N} 或 {"error": "..."}
    """
    try:
        target = _safe_path(path)
        if not target.exists():
            return json.dumps({"error": f"文件不存在: {path}"}, ensure_ascii=False)
        if not target.is_file():
            return json.dumps({"error": f"不是文件: {path}"}, ensure_ascii=False)

        size = target.stat().st_size
        if size > _MAX_READ_BYTES:
            return json.dumps(
                {"error": f"文件过大 ({size} bytes)，最大 {_MAX_READ_BYTES} bytes"},
                ensure_ascii=False,
            )

        try:
            text = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return json.dumps(
                {"error": "无法以文本方式读取（可能是二进制文件）"},
                ensure_ascii=False,
            )

        if len(text) > max_chars:
            text = text[:max_chars] + f"\n... (截断，共 {len(text)} 字符)"
        return json.dumps(
            {"ok": True, "content": text, "size": size},
            ensure_ascii=False,
        )
    except ValueError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"读取失败: {e}"}, ensure_ascii=False)


@tool
def write_file(path: str, content: str) -> str:
    """将文本内容写入 store/agent/ 下指定路径的文件（覆盖写入）。

    Args:
        path: store 目录下的相对路径
        content: 要写入的文本内容

    Returns:
        {"ok": true, "path": "...", "size": N} 或 {"error": "..."}
    """
    try:
        target = _safe_path(path)
        os.makedirs(target.parent, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return json.dumps(
            {"ok": True, "path": path, "size": len(content)},
            ensure_ascii=False,
        )
    except ValueError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"写入失败: {e}"}, ensure_ascii=False)


@tool
def delete_file(path: str) -> str:
    """删除 store/agent/ 下指定的文件。

    Args:
        path: store 目录下的相对路径

    Returns:
        {"ok": true, "path": "..."} 或 {"error": "..."}
    """
    try:
        target = _safe_path(path)
        if not target.exists():
            return json.dumps({"error": f"文件不存在: {path}"}, ensure_ascii=False)
        target.unlink()
        return json.dumps({"ok": True, "path": path}, ensure_ascii=False)
    except ValueError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"删除失败: {e}"}, ensure_ascii=False)


# ── 目录工具 ──────────────────────────────────────────────

@tool
def list_directory(path: str = "") -> str:
    """列出 store/agent/ 下指定目录的文件和子目录。

    Args:
        path: store 目录下的相对路径，空字符串表示 store 根目录

    Returns:
        {"ok": true, "path": "...", "items": [{"name":"...", "type":"file|dir", "size":N}, ...]}
    """
    try:
        target = _safe_path(path) if path else _STORE_ROOT
        if not target.exists():
            return json.dumps({"error": f"目录不存在: {path or '/'}"}, ensure_ascii=False)
        if not target.is_dir():
            return json.dumps({"error": f"不是目录: {path or '/'}"}, ensure_ascii=False)

        items = []
        for entry in sorted(target.iterdir(), key=lambda e: (e.is_file(), e.name)):
            items.append({
                "name": entry.name,
                "type": "dir" if entry.is_dir() else "file",
                "size": entry.stat().st_size if entry.is_file() else 0,
            })
        return json.dumps(
            {"ok": True, "path": path or "/", "count": len(items), "items": items},
            ensure_ascii=False,
        )
    except ValueError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"列目录失败: {e}"}, ensure_ascii=False)
