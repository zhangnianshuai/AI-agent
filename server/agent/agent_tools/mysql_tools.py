"""
MySQL 管理工具集 —— 仅 Admin Agent 使用
"""

import json

from langchain_core.tools import tool
from server.dao.database import db
from server.utils.sql_guard import SQLGuardError, validate_readonly_query


@tool
def update_status(table: str, record_id: int, status: int) -> str:
    """查询并修改指定表中的记录状态。先搜索确认记录存在，再执行状态更新。

    支持的表和状态值：
    - user: status 0=禁用, 1=正常
    - job_position: status 0=关闭, 1=上架, 2=下架
    - company: status 0=停用, 1=正常

    Args:
        table: 表名（user / job_position / company）
        record_id: 记录ID
        status: 新状态值（0/1/2 视表而定）

    Returns:
        {"ok": true, "message": "...", "before": {...}, "after": {...}} 或 {"error": "..."}
    """
    allowed = {
        "user": {
            "valid": (0, 1),
            "name_field": "username",
            "status_labels": {0: "禁用", 1: "正常"},
            "extra_check": lambda row: "不能封禁管理员" if row.get("role") == "admin" else None,
        },
        "job_position": {
            "valid": (0, 1, 2),
            "name_field": "title",
            "status_labels": {0: "关闭", 1: "上架", 2: "下架"},
            "extra_check": None,
        },
        "company": {
            "valid": (0, 1),
            "name_field": "name",
            "status_labels": {0: "停用", 1: "正常"},
            "extra_check": None,
        },
    }

    if table not in allowed:
        return json.dumps(
            {"error": f"不支持的表 '{table}'，可选: {list(allowed.keys())}"},
            ensure_ascii=False,
        )

    cfg = allowed[table]
    if status not in cfg["valid"]:
        return json.dumps(
            {"error": f"表 '{table}' 不支持状态值 {status}，可选: {list(cfg['valid'])}"},
            ensure_ascii=False,
        )

    # 预编译 SQL（防注入：table 已由 whitelist 验证）
    _SQL = {
        "user":         ("SELECT id,username,role,status FROM user WHERE id = %s",
                         "UPDATE user SET status = %s WHERE id = %s"),
        "job_position": ("SELECT id,title,status FROM job_position WHERE id = %s",
                         "UPDATE job_position SET status = %s WHERE id = %s"),
        "company":      ("SELECT id,name,status FROM company WHERE id = %s",
                         "UPDATE company SET status = %s WHERE id = %s"),
    }

    try:
        select_sql, update_sql = _SQL[table]
        # 1) 搜索 — 确认记录存在
        row = db.query(select_sql, params=(record_id,), one=True)
        if not row:
            return json.dumps(
                {"error": f"表 '{table}' 中未找到 id={record_id} 的记录"},
                ensure_ascii=False,
            )

        # 2) 额外校验（如不能封禁管理员）
        if cfg["extra_check"]:
            err = cfg["extra_check"](row)
            if err:
                return json.dumps({"error": err}, ensure_ascii=False)

        old_status = row.get("status")
        if old_status == status:
            name = row.get(cfg["name_field"], record_id)
            label = cfg["status_labels"].get(status, status)
            return json.dumps(
                {"ok": True, "message": f"「{name}」已是{label}状态，无需重复操作"},
                ensure_ascii=False,
            )

        # 3) 执行更新
        db.execute(update_sql, (status, record_id))

        name = row.get(cfg["name_field"], record_id)
        old_label = cfg["status_labels"].get(old_status, old_status)
        new_label = cfg["status_labels"].get(status, status)

        return json.dumps(
            {
                "ok": True,
                "message": f"已将「{name}」从 {old_label} 改为 {new_label}",
                "before": {"id": record_id, "status": old_status},
                "after": {"id": record_id, "status": status},
            },
            ensure_ascii=False, default=str,
        )

    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ── query_mysql 只读安全策略 ──────────────────────────────
_ALLOWED_TABLES = {
    "user", "company", "job_position", "interview_session",
    "interview_record", "interview_evaluation", "resume",
    "agent_config", "user_company",
}
_MAX_ROWS = 200
_DENIED_COLUMNS = {"password_hash"}


@tool
def query_mysql(sql_query: str) -> str:
    """执行受限 MySQL 只读查询并返回 JSON。

    查询会先经过 SQL Guard：仅允许单条 SELECT，解析所有 FROM/JOIN 表并执行
    白名单校验，禁止 UNION/CTE/子查询/危险函数/锁定读取，并强制限制结果集大小。

    Args:
        sql_query: 完整 SELECT 查询语句

    Returns:
        {"count": N, "rows": [...], "tables": [...]} 或 {"error": "..."}
    """
    try:
        validated = validate_readonly_query(
            sql_query,
            allowed_tables=_ALLOWED_TABLES,
            max_rows=_MAX_ROWS,
            denied_columns=_DENIED_COLUMNS,
        )
    except SQLGuardError as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)

    try:
        rows = db.query(validated.sql)
        return json.dumps(
            {
                "count": len(rows),
                "rows": rows,
                "tables": list(validated.tables),
                "limit": validated.limit,
            },
            ensure_ascii=False,
            default=str,
        )
    except Exception as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)

