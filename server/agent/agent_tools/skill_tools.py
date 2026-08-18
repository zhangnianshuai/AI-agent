"""
技能工具 — 读取 agent_skills/ 下的 SKILL.md，供 LLM 了解并执行技能。

返回的技能内容中，skills/ 路径会被替换为绝对路径，LLM 可直接运行其中的命令。
"""

import os

from langchain_core.tools import tool

_SKILLS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agent_skills")


@tool
def get_skills_list() -> str:
    """获取 agent_skills/ 下所有技能的简要描述。

    Returns:
        每个技能一行：name: frontmatter 描述
    """
    if not os.path.exists(_SKILLS_DIR):
        return "（agent_skills 目录不存在）"

    out = ""
    for name in sorted(os.listdir(_SKILLS_DIR)):
        md = os.path.join(_SKILLS_DIR, name, "SKILL.md")
        if not os.path.isfile(md):
            continue
        try:
            with open(md, "r", encoding="utf-8") as f:
                text = f.read()
            parts = text.split("---")
            desc = parts[1].strip() if len(parts) >= 2 else "(无描述)"
            out += f"{name}: {desc}\n"
        except Exception:
            out += f"{name}: (读取失败)\n"
    return out.strip() or "（无可用技能）"


@tool
def get_skill_content(skill_name: str) -> str:
    """获取指定技能的完整 SKILL.md 内容（含使用说明和执行命令）。

    Args:
        skill_name: 技能名称（目录名），如 "tavily-search"

    Returns:
        SKILL.md 正文（skills/ 路径已替换为绝对路径）
    """
    md = os.path.join(_SKILLS_DIR, skill_name, "SKILL.md")
    if not os.path.isfile(md):
        return f"技能 '{skill_name}' 不存在。先调用 get_skills_list 查看可用技能。"

    try:
        with open(md, "r", encoding="utf-8") as f:
            text = f.read()
        parts = text.split("---")
        body = parts[2].strip() if len(parts) >= 3 else text.strip()

        # 将 skills/ 相对路径替换为绝对路径，LLM 可直接执行
        body = body.replace("skills/", _SKILLS_DIR.replace("\\", "/") + "/")
        return body
    except Exception as e:
        return f"读取失败: {e}"
