---
name: create-skill
description: "创建一个新的skill。当用户要求创建新技能、新建skill、添加功能模块时使用。会生成完整的SKILL.md和可选的脚本模板。"
---

# 创建 Skill

用于在 agent_skills 目录下创建一个完整的技能模块。

## 执行命令

```bash
# 创建纯提示词技能（默认类型 — 仅生成 SKILL.md）
python agent_skills/create-skill/scripts/create_skill.py --name "技能名称" --description "一句话描述"

# 创建带 Python 脚本的技能（同时生成 scripts/ 目录及入口脚本）
python agent_skills/create-skill/scripts/create_skill.py --name "技能名称" --description "一句话描述" --with-scripts

# 创建带参考文档目录的技能
python agent_skills/create-skill/scripts/create_skill.py --name "技能名称" --description "描述" --with-references

# 自定义 SKILL.md 正文内容
python agent_skills/create-skill/scripts/create_skill.py --name "技能名称" --description "描述" --body "## 自定义标题\n..."

# JSON 格式输出（便于脚本调用）
python agent_skills/create-skill/scripts/create_skill.py --name "demo" --description "演示" --format json
```

## 参数说明

| 参数 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| --name | 是 | - | 技能名称，英文 kebab-case，如 `weather-query` |
| --description | 是 | - | 一句话描述技能的用途 |
| --body | 否 | 自动生成 | SKILL.md 正文（Markdown），不填则按模板自动生成 |
| --skill-type | 否 | prompt | 技能类型：`prompt`（纯提示词）或 `scripted`（含脚本） |
| --with-scripts | 否 | - | 同时创建 scripts/ 目录和入口脚本模板 |
| --script-name | 否 | main.py | 入口脚本文件名，仅 scripted 类型生效 |
| --with-references | 否 | - | 同时创建 references/ 目录用于存放参考文档 |
| --format | 否 | text | 输出格式：`text`（人类可读）或 `json`（机器可解析） |

## 输出

创建成功后返回新 skill 的路径和文件列表。

## 注意事项

- 技能名称必须符合 kebab-case 格式（小写字母 + 连字符），如 `weather-query`、`code-reviewer`
- 创建后 LLM 需要根据实际需求完善脚本中的 `process()` 函数
- 参考文档放入 `references/` 目录后，Claude 调用技能时会自动加载
