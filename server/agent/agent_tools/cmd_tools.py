"""
命令行工具集 — Windows 系统命令的安全封装

仅供 SQL Agent（admin）使用。安全设计：
- cmd_execute: 通用命令执行，白名单 + 危险字符拦截
- 高层工具: 服务管理 / 日志查看 / 系统资源 / 健康检查
"""

import json
import logging
import re
import subprocess
from pathlib import Path

from langchain_core.tools import tool

# ── 全局限制 ──────────────────────────────────────────────

_CMD_TIMEOUT = 30          # 单次命令超时（秒）
_MAX_OUTPUT_CHARS = 8192   # 输出字符上限

_audit = logging.getLogger("agent.audit.cmd")


# ── 编码处理（Windows GBK / UTF-8 兼容）───────────────────

def _safe_decode(data: bytes) -> str:
    """UTF-8 优先，GBK 兜底，最终 replace 保底"""
    for enc in ['utf-8', 'gbk']:
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return data.decode('utf-8', errors='replace')


# ── 内部执行函数 ──────────────────────────────────────────

def _run(command: str, timeout: int = _CMD_TIMEOUT) -> dict:
    """执行 shell 命令，返回统一结构。

    与用户提供的参考实现一致：shell=True + 手动解码。
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=False,
            timeout=timeout,
        )
        stdout = _safe_decode(result.stdout).strip()
        stderr = _safe_decode(result.stderr).strip()
        return {
            "ok": result.returncode == 0,
            "stdout": stdout,
            "stderr": stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": f"命令超时 ({timeout}s)", "returncode": -1}
    except Exception as e:
        return {"ok": False, "stdout": "", "stderr": str(e), "returncode": -1}


def _truncate(text: str, max_chars: int = _MAX_OUTPUT_CHARS) -> str:
    """截断过长文本"""
    if len(text) > max_chars:
        return text[:max_chars] + f"\n... (截断，共 {len(text)} 字符)"
    return text


# ── cmd_execute 安全校验 ──────────────────────────────────

# 允许的命令前缀白名单（正则，匹配命令名）
_CMD_WHITELIST = [
    r"^dir\b", r"^type\b", r"^echo\b", r"^findstr\b",
    r"^tasklist\b", r"^systeminfo\b", r"^ipconfig\b",
    r"^ping\b", r"^nslookup\b", r"^whoami\b", r"^hostname\b",
    r"^ver\b", r"^date\b", r"^time\b", r"^netstat\b",
    r"^sc\s+query\b", r"^net\s+(start|stop)\b",
    r"^wmic\b", r"^schtasks\s+/query\b",
    r"^where\b", r"^set\b",
    r"^curl\b", r"^python\b", r"^cd\b",
    r"^get-process\b", r"^get-service\b",    # PowerShell
]

# 禁止的 shell 元字符（防命令链注入）
_DANGEROUS_CHARS = re.compile(r'[;&|`$(){}\[\]<>!\n\r]')

# 禁止的危险命令关键字（即使匹配白名单也拒绝）
# 注意：这些模式匹配整个命令字符串，不仅是命令名，所以要足够精确避免误伤参数
_BLOCKED_PATTERNS = [
    # 系统破坏性命令（精确匹配，避免误伤 --format / --delete 等参数）
    r"\bformat\s+\w:",           # format C: / format D: 等磁盘格式化
    r"\bshutdown\b",             # shutdown / shutdown.exe
    r"\bdiskpart\b",             # diskpart
    r"\bbcdedit\b",              # bcdedit
    # 注册表修改
    r"\breg\s+(add|delete|import)\b",
    # 权限修改
    r"\bicacls\b", r"\bcacls\b",
    # 输出重定向（防止覆盖文件）
    r">\s*\S",
    r"2>\s*\S",
]


def _validate_command(command: str) -> str | None:
    """校验命令是否安全。通过返回 None，不通过返回错误信息。"""
    stripped = command.strip()
    if not stripped:
        return "命令为空"

    # 1. 检查危险元字符
    if _DANGEROUS_CHARS.search(stripped):
        return "命令包含禁止的特殊字符 (& | ; ` $ 等)"

    # 2. 白名单匹配
    matched = False
    for pattern in _CMD_WHITELIST:
        if re.match(pattern, stripped, re.IGNORECASE):
            matched = True
            break
    if not matched:
        return f"命令不在允许列表中: {stripped[:60]}"

    # 3. 黑名单二次拦截
    for pattern in _BLOCKED_PATTERNS:
        if re.search(pattern, stripped, re.IGNORECASE):
            return f"命令包含禁止的操作: {pattern}"

    return None


# ── 通用命令执行工具 ──────────────────────────────────────

@tool
def cmd_execute(command: str) -> str:
    """使用命令行执行指定的命令，并返回执行结果。

    安全限制：
    - 仅允许白名单内的命令（dir / type / tasklist / systeminfo / ping 等）
    - 禁止管道、重定向、链式执行等 shell 元字符
    - 禁止 del / format / shutdown 等危险操作

    Args:
        command: 要执行的命令（单条，不含管道/重定向）

    Returns:
        stdout 内容，或错误信息
    """
    err = _validate_command(command)
    if err:
        _audit.warning("cmd_execute BLOCKED: %s — reason: %s", command[:80], err)
        return json.dumps({"error": err, "command": command}, ensure_ascii=False)

    _audit.info("cmd_execute: %s", command[:120])
    r = _run(command)

    if not r["ok"]:
        return f"命令失败 (exit {r['returncode']})\n{r['stderr'] or r['stdout']}"

    return r["stdout"] or "(命令执行成功，但无输出)"


# ── 服务管理（Windows）────────────────────────────────────

# 可查询 / 可重启的 Windows 服务白名单
_ALLOWED_SERVICES = {
    "mysql":     "MySQL",
    "nginx":     "nginx",
    "redis":     "Redis",
}

_RESTARTABLE_SERVICES = ["mysql", "nginx", "redis"]


@tool
def check_service_status(service_name: str) -> str:
    """查看指定 Windows 服务的运行状态。

    Args:
        service_name: 服务名，可选 mysql / nginx / redis

    Returns:
        {"ok": true, "service": "...", "status": "running|stopped|...", "detail": "..."}
    """
    if service_name not in _ALLOWED_SERVICES:
        return json.dumps(
            {"error": f"不支持的服务 '{service_name}'，可选: {list(_ALLOWED_SERVICES.keys())}"},
            ensure_ascii=False,
        )

    svc = _ALLOWED_SERVICES[service_name]
    r = _run(f'sc query "{svc}"', timeout=15)
    _audit.info("check_service_status service=%s rc=%s", service_name, r["returncode"])

    if r["returncode"] != 0:
        return json.dumps({
            "ok": True,
            "service": service_name,
            "status": "not_found" if "1060" in r["stderr"] else "stopped",
            "detail": _truncate(r["stderr"] or r["stdout"]),
        }, ensure_ascii=False)

    # 从 sc query 输出中提取状态
    output = r["stdout"]
    running = "RUNNING" in output.upper() or "4  RUNNING" in output
    return json.dumps({
        "ok": True,
        "service": service_name,
        "status": "running" if running else "stopped",
        "detail": _truncate(output),
    }, ensure_ascii=False)


@tool
def restart_service(service_name: str) -> str:
    """重启指定 Windows 服务（危险操作，仅限白名单）。

    Args:
        service_name: 服务名，可选 mysql / nginx / redis

    Returns:
        {"ok": true, "message": "..."}
    """
    if service_name not in _RESTARTABLE_SERVICES:
        return json.dumps(
            {"error": f"不支持重启 '{service_name}'，可选: {_RESTARTABLE_SERVICES}"},
            ensure_ascii=False,
        )

    svc = _ALLOWED_SERVICES[service_name]

    # 先停止
    stop = _run(f'net stop "{svc}" /y', timeout=60)
    _audit.warning("restart_service service=%s action=stop rc=%s", service_name, stop["returncode"])

    # 再启动
    start = _run(f'net start "{svc}"', timeout=60)
    _audit.warning("restart_service service=%s action=start rc=%s", service_name, start["returncode"])

    if start["ok"]:
        return json.dumps({"ok": True, "message": f"「{service_name}」重启成功"}, ensure_ascii=False)

    return json.dumps({
        "ok": False,
        "message": f"重启失败 (stop rc={stop['returncode']}, start rc={start['returncode']})\n"
                   f"stderr: {start['stderr'] or stop['stderr']}",
    }, ensure_ascii=False)


# ── 日志查看 ──────────────────────────────────────────────

# 允许的日志目录（防止任意文件读取）
_LOG_BASE = Path(__file__).resolve().parent.parent.parent / "logs"
_ALLOWED_LOGS = {
    "app":    _LOG_BASE / "app.log",
    "error":  _LOG_BASE / "error.log",
    "access": _LOG_BASE / "access.log",
}


@tool
def view_log(log_name: str, lines: int = 50) -> str:
    """查看应用日志文件的最近 N 行（用 Python 读取，不依赖外部命令）。

    Args:
        log_name: 日志名，可选 app / error / access
        lines: 返回行数，默认 50，最大 500

    Returns:
        {"ok": true, "log": "...", "lines": N, "content": "..."}
    """
    if log_name not in _ALLOWED_LOGS:
        return json.dumps(
            {"error": f"不支持的日志 '{log_name}'，可选: {list(_ALLOWED_LOGS.keys())}"},
            ensure_ascii=False,
        )

    lines = max(1, min(lines, 500))
    log_path = _ALLOWED_LOGS[log_name]

    _audit.info("view_log log=%s lines=%s", log_name, lines)

    if not log_path.exists():
        return json.dumps(
            {"error": f"日志文件不存在: {log_name}"},
            ensure_ascii=False,
        )

    try:
        # 直接读取文件末尾 N 行（跨平台，不依赖 tail 命令）
        with open(log_path, 'rb') as f:
            # 粗略估算：从末尾读取 lines * 512 字节，通常足够
            chunk_size = lines * 512
            f.seek(0, 2)  # SEEK_END
            file_size = f.tell()
            read_pos = max(0, file_size - chunk_size)
            f.seek(read_pos)
            raw = f.read()
            text = _safe_decode(raw)
            all_lines = text.splitlines()
            last_n = all_lines[-lines:] if len(all_lines) > lines else all_lines
            content = "\n".join(last_n)
    except Exception as e:
        return json.dumps({"error": f"读取日志失败: {e}"}, ensure_ascii=False)

    return json.dumps({
        "ok": True,
        "log": log_name,
        "lines": len(last_n),
        "content": _truncate(content),
    }, ensure_ascii=False)


# ── 系统资源 ──────────────────────────────────────────────

@tool
def check_system_resources() -> str:
    """查看服务器资源概况（磁盘、内存、CPU 负载）。

    Windows 实现，无参数。

    Returns:
        {"ok": true, "disk": "...", "memory": "...", "cpu": "..."}
    """
    # 磁盘使用（C: 盘）
    disk = _run("wmic logicaldisk where DeviceID='C:' get Size,FreeSpace /format:list", timeout=15)

    # 内存
    mem = _run("systeminfo | findstr /C:\"Total Physical Memory\" /C:\"Available Physical Memory\"", timeout=20)

    # CPU 负载
    cpu = _run("wmic cpu get loadpercentage /value", timeout=10)

    _audit.info("check_system_resources")

    return json.dumps({
        "ok": True,
        "disk": _truncate(disk["stdout"] or disk["stderr"], 512),
        "memory": _truncate(mem["stdout"] or mem["stderr"], 1024),
        "cpu": _truncate(cpu["stdout"] or cpu["stderr"], 256),
    }, ensure_ascii=False)


# ── 网络 / 健康检查 ──────────────────────────────────────

# 内部健康检查端点
_ALLOWED_HEALTH_URLS = {
    "agent-api": "http://127.0.0.1:8080/health",
    "admin-api": "http://127.0.0.1:8081/health",
    "milvus":    "http://127.0.0.1:9091/healthz",
}


@tool
def health_check(target: str) -> str:
    """对内部服务执行 HTTP 健康检查（curl GET）。

    Args:
        target: 目标服务标识，可选 agent-api / admin-api / milvus

    Returns:
        {"ok": true, "target": "...", "http_status": 200, "body": "..."}
    """
    if target not in _ALLOWED_HEALTH_URLS:
        return json.dumps(
            {"error": f"不支持的检查目标 '{target}'，可选: {list(_ALLOWED_HEALTH_URLS.keys())}"},
            ensure_ascii=False,
        )

    url = _ALLOWED_HEALTH_URLS[target]
    r = _run(f'curl -s -o nul -w "%{{http_code}}" --max-time 10 {url}', timeout=15)
    _audit.info("health_check target=%s rc=%s", target, r["returncode"])

    # 再从 stdout 取 body（Windows curl 的 -o nul 会把 body 丢弃，仅取 status）
    if r["returncode"] == 0:
        status_code = int(r["stdout"].strip()) if r["stdout"].strip().isdigit() else 0
        # 再请求一次取 body（仅成功时）
        body_r = _run(f"curl -s --max-time 10 {url}", timeout=15)
        body = _truncate(body_r["stdout"], 2048)
    else:
        status_code = 0
        body = r["stderr"]

    return json.dumps({
        "ok": r["returncode"] == 0 and 200 <= status_code < 500,
        "target": target,
        "http_status": status_code,
        "body": body,
    }, ensure_ascii=False)
