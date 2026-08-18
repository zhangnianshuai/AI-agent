"""
创建新 skill 的脚本 — 生成完整的可执行技能模板。

支持两种技能类型：
  - prompt  : 纯提示词技能，仅生成 SKILL.md
  - scripted: 脚本技能，同时生成 SKILL.md + scripts/ 入口脚本

用法:
    # 纯提示词技能（默认）
    python create_skill.py --name "translator" --description "多语言翻译助手"

    # 带脚本的技能
    python create_skill.py --name "weather" --description "天气查询" --with-scripts

    # 自定义 SKILL.md 正文
    python create_skill.py --name "my-tool" --description "自定义工具" --body "## 使用说明\\n..."

    # 带参考文档目录
    python create_skill.py --name "api-wrapper" --description "API 封装" --with-references

    # 机器可读输出
    python create_skill.py --name "demo" --description "演示" --format json
"""

import os
import sys
import argparse
import json
import re
from typing import List, Optional, Dict

# ============================================================================
# 常量定义
# ============================================================================

# 技能名称正则：kebab-case（小写字母开头 + 可选连字符分段）
_SKILL_NAME_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")

# 支持的技能类型
_SKILL_TYPES: Dict[str, str] = {
    "prompt":   "纯 Prompt 技能 — 仅包含 SKILL.md，无脚本",
    "scripted": "脚本技能 — 包含 SKILL.md + scripts/ 入口脚本",
}

# ============================================================================
# 模板定义
# ============================================================================

# --- SKILL.md 正文模板：提示词型技能 ---
# 占位符: {name}, {description}, {usage_example}
_TEMPLATE_BODY_PROMPT = """\
## 功能

{description}

## 触发条件

当用户提到以下关键词或请求时，自动调用此技能：
- 与 **{name}** 相关的任何需求
- {usage_example}

## 执行流程

1. 理解用户的具体需求
2. 按照本技能的规则进行处理
3. 返回结构化结果

## 注意事项

- 确保输出格式符合用户预期
- 遇到不确定的情况，主动询问用户澄清
"""

# --- SKILL.md 正文模板：脚本型技能 ---
# 占位符: {name}, {description}, {script_name}, {usage_example}
_TEMPLATE_BODY_SCRIPTED = """\
## 功能

{description}

## 触发条件

当用户要求 {usage_example} 时调用此技能。

## 执行命令

```bash
python agent_skills/{name}/scripts/{script_name} --input "<输入>" --output "<保存路径>"
```

## 参数

| 参数       | 必填 | 默认值 | 说明                         |
|------------|------|--------|------------------------------|
| --input    | 是   | -      | 输入数据                     |
| --output   | 否   | data/  | 结果保存路径                 |
| --format   | 否   | text   | 输出格式：text 或 json       |

## 输出

执行结果会打印到标准输出，同时保存到指定路径。
"""

# --- 脚本模板：用于生成 scripts/ 下的 Python 入口文件 ---
# 注意：
#   - {name}, {description}, {script_name} 由 .format() 替换
#   - {{name}} 在生成后保留为字面 {name}，由生成的脚本在运行时动态解析
#   - {{ 和 }} 转义为字面花括号（Python dict 语法）
_TEMPLATE_SCRIPT = '''"""
{name} — {description}

用法:
    python {script_name} --input "输入数据" --output "./result.txt"
"""

import argparse
import json
import logging
import os
import sys

# ---- 动态推导技能名称（从脚本路径中提取） ----
# 脚本位于 agent_skills/<skill_name>/scripts/{script_name}
# 向上两级：scripts/ → <skill_name>/
_SKILL_NAME = os.path.basename(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---- 日志配置 ----
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description="{description}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--input", required=True,
        help="输入数据（必填）"
    )
    parser.add_argument(
        "--output", default=None,
        help="结果保存路径（可选，默认保存到 data/ 目录）"
    )
    parser.add_argument(
        "--format", default="text", choices=["text", "json"],
        help="输出格式（默认 text）"
    )
    return parser.parse_args()


def process(input_data: str, output_path: str | None) -> dict:
    """核心处理逻辑 — 在此实现你的业务代码。

    Args:
        input_data:  输入数据
        output_path: 保存路径（None 则自动生成默认路径）

    Returns:
        处理结果字典
    """
    # ---------------------------------------------------------------
    # TODO: 在此实现你的核心逻辑
    #   1. 处理 input_data
    #   2. 调用外部 API / 执行计算 / 生成文件
    #   3. 将结果保存到 output_path
    # ---------------------------------------------------------------

    # ---- 自动生成输出路径 ----
    if output_path is None:
        output_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{{_SKILL_NAME}}_result.txt")

    # ---- 示例：构造返回结果 ----
    result = {{
        "input":  input_data,
        "output": output_path,
        "status": "ok",
        "message": "核心逻辑尚未实现 — 请修改 process() 函数",
    }}

    # ---- 确保输出目录存在并写入文件 ----
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    logger.info("结果已保存至: %s", output_path)
    return result


def output_result(result: dict, fmt: str) -> None:
    """按指定格式输出结果。

    Args:
        result: 处理结果字典
        fmt:    输出格式 — "text" 或 "json"
    """
    if fmt == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for key, value in result.items():
            print(f"{{key:<12}}: {{value}}")


def main() -> None:
    """主入口：解析参数 → 处理 → 输出。"""
    args = parse_args()

    logger.info("开始处理: %s", args.input)

    try:
        result = process(args.input, args.output)
        output_result(result, args.format)
        logger.info("处理完成")
    except Exception as exc:
        logger.error("处理失败: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
'''


# ============================================================================
# 工具函数
# ============================================================================

def validate_skill_name(name: str) -> Optional[str]:
    """校验技能名称是否合法。

    规则（kebab-case）：
    - 长度 2~64 字符
    - 只能包含小写字母、数字和连字符
    - 必须以字母开头，不能以连字符结尾

    Args:
        name: 待校验的技能名称

    Returns:
        合法时返回 None，否则返回错误信息字符串
    """
    if not name:
        return "技能名称不能为空"
    if len(name) < 2:
        return f"技能名称至少 2 个字符，当前 '{name}' 只有 {len(name)} 个"
    if len(name) > 64:
        return f"技能名称不能超过 64 个字符，当前有 {len(name)} 个"
    if not _SKILL_NAME_RE.match(name):
        return (
            "技能名称格式不合法。请使用 kebab-case 格式：\n"
            "  - 只能包含小写字母、数字和连字符 (-)\n"
            "  - 必须以小写字母开头\n"
            "  - 不能以连字符结尾\n"
            "  - 正确示例：weather-query、code-reviewer、data-export-v2\n"
            "  - 错误示例：Weather、my_skill、-tool、tool-"
        )
    return None


def resolve_agent_skills_root() -> str:
    """推导 agent_skills 根目录的绝对路径。

    本脚本位于 agent_skills/<skill-name>/scripts/ 下，
    向上两级即为 agent_skills/ 根目录。

    Returns:
        agent_skills 目录的绝对路径
    """
    scripts_dir = os.path.dirname(os.path.abspath(__file__))   # .../scripts
    skill_dir = os.path.dirname(scripts_dir)                    # .../<skill-name>
    return os.path.dirname(skill_dir)                           # .../agent_skills


def emit(success: bool, path: str, files: List[str],
         error: str = "", fmt: str = "text") -> None:
    """统一输出执行结果（同时支持人类可读和机器可解析两种格式）。

    Args:
        success: 操作是否成功
        path:    技能目录的绝对路径
        files:   已创建的文件相对路径列表
        error:   错误信息（仅在 success=False 时使用）
        fmt:     输出格式 — "text" 或 "json"
    """
    if fmt == "json":
        output: dict = {"success": success, "path": path, "files": files}
        if error:
            output["error"] = error
        print(json.dumps(output, ensure_ascii=False))
    else:
        if success:
            print(f"\n[OK] 技能创建成功!")
            print(f"   路径: {path}")
            print(f"   文件:")
            for f in files:
                print(f"     - {f}")
        else:
            print(f"\n[ERROR] {error}")


def write_skill_md(skill_dir: str, name: str, description: str,
                   body: str, skill_type: str, script_name: str) -> str:
    """生成 SKILL.md 文件。

    优先使用用户自定义正文（--body），否则根据技能类型选择对应的默认模板。

    Args:
        skill_dir:   技能目录的绝对路径
        name:        技能名称
        description: 技能描述（写入 YAML frontmatter）
        body:        用户自定义正文（为空则自动生成）
        skill_type:  技能类型 — "prompt" | "scripted"
        script_name: 脚本文件名（仅 scripted 类型使用）

    Returns:
        相对路径字符串，如 "my-skill/SKILL.md"
    """
    # ---- 确定正文内容 ----
    if body:
        body_section = body.strip()
    elif skill_type == "scripted":
        body_section = _TEMPLATE_BODY_SCRIPTED.format(
            name=name,
            description=description,
            usage_example=f"进行{{某项操作}}",
            script_name=script_name,
        )
    else:
        body_section = _TEMPLATE_BODY_PROMPT.format(
            name=name,
            description=description,
            usage_example=f"进行与 {name} 相关的操作",
        )

    # ---- 组装 SKILL.md：YAML frontmatter + 正文 ----
    content = (
        f"---\n"
        f"name: {name}\n"
        f'description: "{description}"\n'
        f"---\n"
        f"\n"
        f"{body_section}\n"
    )

    filepath = os.path.join(skill_dir, "SKILL.md")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    return f"{name}/SKILL.md"


def write_scripts(skill_dir: str, name: str, description: str,
                  script_name: str) -> List[str]:
    """创建 scripts/ 目录并写入入口脚本模板。

    Args:
        skill_dir:   技能目录的绝对路径
        name:        技能名称
        description: 技能描述
        script_name: 脚本文件名（如 "main.py"）

    Returns:
        创建的文件/目录相对路径列表
    """
    created: List[str] = []

    scripts_dir = os.path.join(skill_dir, "scripts")
    os.makedirs(scripts_dir, exist_ok=True)
    created.append(f"{name}/scripts/")

    # ---- 填充脚本模板并写入 ----
    script_content = _TEMPLATE_SCRIPT.format(
        name=name,
        description=description,
        script_name=script_name,
    )
    script_path = os.path.join(scripts_dir, script_name)
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script_content)
    created.append(f"{name}/scripts/{script_name}")

    return created


def write_references(skill_dir: str, name: str) -> str:
    """创建 references/ 目录及 README，用于存放参考文档。

    Args:
        skill_dir: 技能目录的绝对路径
        name:      技能名称

    Returns:
        相对路径字符串
    """
    refs_dir = os.path.join(skill_dir, "references")
    os.makedirs(refs_dir, exist_ok=True)

    # ---- 写入 references/README.md ----
    readme_path = os.path.join(refs_dir, "README.md")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(
            f"# {name} 参考资源\n"
            f"\n"
            f"此目录存放 **{name}** 技能所需的参考资料。\n"
            f"\n"
            f"## 使用方式\n"
            f"\n"
            f"将参考文档（API 文档、数据格式说明、示例文件等）放入此目录，\n"
            f"Claude 在调用技能时会自动加载这些参考内容。\n"
        )

    return f"{name}/references/"


# ============================================================================
# 主入口
# ============================================================================

def main() -> None:
    """解析命令行参数，创建 skill 目录结构。"""

    # ---- CLI 参数定义 ----
    parser = argparse.ArgumentParser(
        description="创建一个新的 Claude Code skill（生成完整模板）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
示例:
  # 纯提示词技能（默认类型）
  %(prog)s --name "translator" --description "多语言翻译助手"

  # 带 Python 脚本的技能
  %(prog)s --name "weather" --description "天气查询" --with-scripts

  # 自定义 SKILL.md 正文
  %(prog)s --name "my-tool" --description "自定义工具" --body "# 标题\\n\\n内容..."

  # 同时创建参考文档目录
  %(prog)s --name "api-wrapper" --description "API 封装" --with-references

  # JSON 输出（便于其他脚本调用）
  %(prog)s --name "demo" --description "演示技能" --format json
        """,
    )

    # -- 必填参数 --
    parser.add_argument(
        "--name", required=True,
        metavar="NAME",
        help="技能名称，用作文件夹名。建议英文 kebab-case，如 'weather-query'"
    )
    parser.add_argument(
        "--description", required=True,
        metavar="DESC",
        help="技能描述，一句话说明用途（写入 SKILL.md 的 YAML frontmatter）"
    )

    # -- 可选参数 --
    parser.add_argument(
        "--body", default="",
        metavar="MARKDOWN",
        help="SKILL.md 正文内容（Markdown 格式）。不填则根据 --skill-type 自动生成模板"
    )
    parser.add_argument(
        "--skill-type", default="prompt",
        choices=list(_SKILL_TYPES.keys()),
        help="技能类型。prompt=纯提示词（默认），scripted=含脚本模板"
    )
    parser.add_argument(
        "--with-scripts", action="store_true",
        help="同时创建 scripts/ 目录和入口脚本（等价于 --skill-type scripted）"
    )
    parser.add_argument(
        "--script-name", default="main.py",
        metavar="FILE",
        help="入口脚本文件名（默认 main.py），仅 scripted 类型生效"
    )
    parser.add_argument(
        "--with-references", action="store_true",
        help="同时创建 references/ 目录用于存放参考文档"
    )
    parser.add_argument(
        "--format", default="text", choices=["text", "json"],
        help="输出格式。text=人类可读（默认），json=机器可解析"
    )

    args = parser.parse_args()

    # ---- 参数后处理：--with-scripts 隐式设定 skill_type ----
    if args.with_scripts:
        args.skill_type = "scripted"

    # ---- 1. 校验技能名称 ----
    validation_error = validate_skill_name(args.name)
    if validation_error:
        emit(success=False, path="", files=[], error=validation_error, fmt=args.format)
        sys.exit(1)

    # ---- 2. 推导目标路径 ----
    agent_skills_root = resolve_agent_skills_root()
    new_skill_dir = os.path.join(agent_skills_root, args.name)

    # ---- 3. 检查技能是否已存在 ----
    if os.path.exists(new_skill_dir):
        emit(
            success=False, path=new_skill_dir, files=[],
            error=f"技能 '{args.name}' 已存在于 {new_skill_dir}，请先删除或使用其他名称",
            fmt=args.format,
        )
        sys.exit(1)

    # ---- 4. 创建目录结构 ----
    created: List[str] = []

    try:
        # 创建技能根目录
        os.makedirs(new_skill_dir, exist_ok=True)

        # 4a. SKILL.md（必须）
        skill_md_rel = write_skill_md(
            new_skill_dir, args.name, args.description,
            args.body, args.skill_type, args.script_name,
        )
        created.append(skill_md_rel)

        # 4b. scripts/（仅 scripted 类型）
        if args.skill_type == "scripted":
            created.extend(
                write_scripts(new_skill_dir, args.name, args.description, args.script_name)
            )

        # 4c. references/（可选）
        if args.with_references:
            created.append(write_references(new_skill_dir, args.name))

        # ---- 5. 成功输出 ----
        emit(success=True, path=new_skill_dir, files=created, fmt=args.format)

    except OSError as exc:
        # 文件系统错误（权限不足、磁盘满等）
        emit(
            success=False, path=new_skill_dir, files=created,
            error=f"文件操作失败: {exc}", fmt=args.format,
        )
        sys.exit(1)
    except Exception as exc:
        # 其他未预期错误
        emit(
            success=False, path=new_skill_dir, files=created,
            error=f"未知错误: {exc}", fmt=args.format,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
