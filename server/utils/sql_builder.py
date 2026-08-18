"""
SQL 动态拼接工具 — 所有子句构建收口于此，杜绝手拼 SQL 带来的注入风险。
"""

from typing import Any


def build_where(
    filters: dict[str, Any],
    field_map: dict[str, str] | None = None,
    *,
    like_fields: set[str] | None = None,
    prefix: str = "WHERE",
    alias: str = "",
) -> tuple[str, list]:
    """
    动态构建 WHERE 子句，返回 (子句, 参数列表)。

    Parameters
    ----------
    filters : dict
        调用方传入的筛选参数，如 {"keyword": "python", "location": "北京"}。
        None 值会被自动跳过。
    field_map : dict, optional
        参数名 → SQL 表达式的映射。表达式中用 %s 占位。
        如 {"keyword": "j.title LIKE %s", "location": "j.location = %s"}。
        未在 map 中的 key 会被忽略。
    like_fields : set, optional
        值需要自动包 %% 的字段名集合，如 {"keyword"}。
    prefix : str
        子句前缀，默认 "WHERE"，也可传空字符串（用于已有 WHERE 的追加）。
    alias : str
        表别名前缀，如 "j."。会自动加到 like_fields 不属于 field_map 兜底时。

    Returns
    -------
    (str, list)
        如 ("WHERE j.title LIKE %s AND j.location = %s", ["%python%", "北京"])
        如无有效条件则返回 ("", [])

    Examples
    --------
    >>> build_where(
    ...     {"keyword": "go", "company_id": 5, "x": None},
    ...     {"keyword": "j.title LIKE %s", "company_id": "j.company_id = %s"},
    ...     like_fields={"keyword"},
    ... )
    ("WHERE j.title LIKE %s AND j.company_id = %s", ["%go%", 5])
    """
    if not filters or not field_map:
        return "", []

    conditions: list[str] = []
    params: list = []
    like = like_fields or set()
    a = f"{alias}." if alias else ""

    for key, expr in field_map.items():
        val = filters.get(key)
        if val is None:
            continue
        conditions.append(expr)
        wrapped = f"%{val}%" if key in like else val
        # 自动匹配 expr 中 %s 的数量（处理 LIKE+OR 需要同一值填多个占位符的场景）
        n = expr.count("%s")
        params.extend([wrapped] * n if n > 1 else [wrapped])

    if not conditions:
        return "", []

    return f"{prefix} " + " AND ".join(conditions), params


def build_set(**kwargs: Any) -> tuple[str, list]:
    """
    动态构建 SET 子句，跳过 None 值。
    返回 ("field1 = %s, field2 = %s", [val1, val2])

    Examples
    --------
    >>> build_set(title="abc", salary_min=None, headcount=3)
    ("title = %s, headcount = %s", ["abc", 3])
    """
    fields: list[str] = []
    params: list = []

    for field, val in kwargs.items():
        if val is not None:
            fields.append(f"{field} = %s")
            params.append(val)

    if not fields:
        return "", []

    return ", ".join(fields), params
