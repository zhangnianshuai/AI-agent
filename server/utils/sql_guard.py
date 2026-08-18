"""Conservative SQL guard for LLM-generated admin queries.

This module intentionally supports a restricted SELECT grammar instead of trying to
accept every valid MySQL statement. LLM-generated SQL should fail closed: complex
constructs that are hard to authorize safely (UNION, CTEs, nested SELECTs,
comma-joins, locking clauses) are rejected and the Agent can regenerate a simpler
query.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


class SQLGuardError(ValueError):
    pass


@dataclass(frozen=True)
class ValidatedQuery:
    sql: str
    tables: tuple[str, ...]
    limit: int


_COMMENT_RE = re.compile(r"(--[^\n]*|#[^\n]*|/\*.*?\*/)", re.DOTALL)
_TABLE_RE = re.compile(
    r"\b(?:FROM|JOIN)\s+(`?[A-Za-z_][A-Za-z0-9_]*`?(?:\s*\.\s*`?[A-Za-z_][A-Za-z0-9_]*`?)?)",
    re.IGNORECASE,
)
_LIMIT_RE = re.compile(r"\bLIMIT\s+(\d+)(?:\s+OFFSET\s+(\d+))?\b", re.IGNORECASE)
_FORBIDDEN_TOKEN_RE = re.compile(
    r"\b(?:INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|REPLACE|CALL|EXECUTE|"
    r"GRANT|REVOKE|UNION|INTERSECT|EXCEPT|WITH|INTO|OUTFILE|DUMPFILE|LOAD|"
    r"INFORMATION_SCHEMA|PERFORMANCE_SCHEMA|SYS|MYSQL)\b",
    re.IGNORECASE,
)
_FORBIDDEN_FUNCTION_RE = re.compile(
    r"\b(?:SLEEP|BENCHMARK|LOAD_FILE)\s*\(", re.IGNORECASE
)
_LOCK_RE = re.compile(r"\bFOR\s+UPDATE\b|\bLOCK\s+IN\s+SHARE\s+MODE\b", re.IGNORECASE)
_NESTED_SELECT_RE = re.compile(r"\(\s*SELECT\b", re.IGNORECASE)


def _mask_string_literals(sql: str) -> str:
    """Replace quoted string contents with spaces while preserving positions."""
    chars = list(sql)
    quote: str | None = None
    escaped = False
    i = 0
    while i < len(chars):
        ch = chars[i]
        if quote is None:
            if ch in ("'", '"'):
                quote = ch
                chars[i] = " "
            i += 1
            continue

        if escaped:
            chars[i] = " "
            escaped = False
            i += 1
            continue
        if ch == "\\":
            chars[i] = " "
            escaped = True
            i += 1
            continue
        if ch == quote:
            chars[i] = " "
            quote = None
            i += 1
            continue
        chars[i] = " "
        i += 1

    if quote is not None:
        raise SQLGuardError("SQL 字符串字面量未闭合")
    return "".join(chars)


def _normalize_table(raw: str) -> str:
    raw = re.sub(r"\s+", "", raw).replace("`", "")
    if "." in raw:
        raise SQLGuardError("不允许跨数据库/Schema 查询")
    return raw.lower()


def _reject_comma_join(masked: str):
    """Reject `FROM a, b`; explicit JOIN is easier to authorize consistently."""
    match = re.search(r"\bFROM\b(.*?)(?:\bWHERE\b|\bGROUP\b|\bORDER\b|\bLIMIT\b|$)", masked, re.I | re.S)
    if match and "," in match.group(1):
        raise SQLGuardError("不允许逗号连接，请使用显式 JOIN")


def validate_readonly_query(
    sql: str,
    allowed_tables: Iterable[str],
    max_rows: int = 200,
    denied_columns: Iterable[str] = (),
) -> ValidatedQuery:
    """Validate and normalize an LLM-generated read-only query.

    Security policy:
    - one SELECT statement only;
    - all FROM/JOIN tables must be in the whitelist;
    - no cross-schema access, nested SELECT, UNION/CTE, comments or locking reads;
    - dangerous MySQL functions and denied columns are rejected;
    - wildcard SELECT is rejected (except COUNT(*));
    - LIMIT is mandatory and capped to ``max_rows``.
    """
    if not isinstance(sql, str) or not sql.strip():
        raise SQLGuardError("SQL 不能为空")

    query = sql.strip()
    masked = _mask_string_literals(query)

    # Only a final statement terminator is allowed. Semicolons/comments inside
    # quoted literals were masked above and therefore do not create false positives.
    if masked.rstrip().endswith(";"):
        cut = masked.rfind(";")
        query = query[:cut].rstrip()
        masked = masked[:cut].rstrip()
    if ";" in masked:
        raise SQLGuardError("一次只允许执行一条 SQL")
    if _COMMENT_RE.search(masked):
        raise SQLGuardError("查询中不允许 SQL 注释")
    if not re.match(r"^\s*SELECT\b", masked, re.IGNORECASE):
        raise SQLGuardError("仅允许执行 SELECT 查询")
    if _FORBIDDEN_TOKEN_RE.search(masked):
        raise SQLGuardError("查询包含不允许的 SQL 结构")
    if _FORBIDDEN_FUNCTION_RE.search(masked):
        raise SQLGuardError("查询包含不允许的数据库函数")
    if _LOCK_RE.search(masked):
        raise SQLGuardError("不允许锁定式读取")
    if _NESTED_SELECT_RE.search(masked):
        raise SQLGuardError("暂不允许子查询，请改写为白名单表的显式 JOIN")

    _reject_comma_join(masked)

    select_match = re.match(r"^\s*SELECT\s+(.*?)\s+FROM\b", masked, re.IGNORECASE | re.DOTALL)
    if not select_match:
        raise SQLGuardError("无法解析 SELECT 字段列表")
    select_clause = select_match.group(1)
    select_without_count = re.sub(r"COUNT\s*\(\s*\*\s*\)", "", select_clause, flags=re.IGNORECASE)
    if "*" in select_without_count:
        raise SQLGuardError("不允许 SELECT *，请显式指定需要的字段")

    denied = {str(c).lower() for c in denied_columns}
    for column in denied:
        if re.search(rf"(?<![A-Za-z0-9_])`?{re.escape(column)}`?(?![A-Za-z0-9_])", masked, re.IGNORECASE):
            raise SQLGuardError(f"字段 '{column}' 不允许通过 Agent 查询")

    tables = tuple(dict.fromkeys(_normalize_table(m.group(1)) for m in _TABLE_RE.finditer(masked)))
    if not tables:
        raise SQLGuardError("查询缺少可识别的 FROM/JOIN 表")

    allowed = {str(t).lower() for t in allowed_tables}
    denied = [table for table in tables if table not in allowed]
    if denied:
        raise SQLGuardError(f"存在未授权表: {', '.join(denied)}")

    limit_matches = list(_LIMIT_RE.finditer(masked))
    if len(limit_matches) > 1:
        raise SQLGuardError("LIMIT 子句异常")

    if not limit_matches:
        final_limit = max_rows
        query = f"{query} LIMIT {max_rows}"
    else:
        match = limit_matches[0]
        requested = int(match.group(1))
        final_limit = min(max(requested, 1), max_rows)
        if requested != final_limit:
            start, end = match.span(1)
            query = query[:start] + str(final_limit) + query[end:]

    return ValidatedQuery(sql=query, tables=tables, limit=final_limit)
