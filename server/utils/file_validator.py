"""
文件上传校验工具 —— 文件格式 + 业务实体存在性。

校验链路（按顺序）：
  1. validate_entity()   → 公司/岗位/用户是否存在
  2. read_and_validate_upload() → 扩展名 → Content-Type → 非空
"""

import functools
from pathlib import Path
from typing import Optional, Set

from fastapi import UploadFile

from server.models.result import Result

# ═══════════════════════════════════════════════════════════
# 预定义格式组
# ═══════════════════════════════════════════════════════════

PDF_EXTENSIONS = {".pdf"}
PDF_CONTENT_TYPES = {"application/pdf"}

WORD_EXTENSIONS = {".docx", ".doc"}
WORD_CONTENT_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
}

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
IMAGE_CONTENT_TYPES = {
    "image/png", "image/jpeg", "image/gif",
    "image/webp", "image/svg+xml",
}

# ═══════════════════════════════════════════════════════════
# 文件格式校验
# ═══════════════════════════════════════════════════════════

async def read_and_validate_upload(
    file: UploadFile,
    allowed_extensions: Set[str],
    allowed_content_types: Set[str],
) -> tuple[Optional[Result], bytes]:
    """校验上传文件格式并返回文件字节。

    校验链路：扩展名 → Content-Type → 非空。
    - 错误结果不为 None → 直接返回错误，bytes 无意义
    - 错误结果为 None → bytes 为已读取的文件内容
    """
    if not file.filename:
        return Result.fail(code=400, message="文件名为空"), b""

    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_extensions:
        return Result.fail(
            code=400,
            message=f"仅支持 {', '.join(sorted(allowed_extensions))} 格式的文件，当前格式: {ext}",
        ), b""

    if file.content_type not in allowed_content_types:
        return Result.fail(
            code=400,
            message=f"文件类型不匹配，当前类型: {file.content_type}",
        ), b""

    file_bytes = await file.read()
    if not file_bytes:
        return Result.fail(code=400, message="上传的文件为空，请检查文件内容"), b""

    return None, file_bytes


# ═══════════════════════════════════════════════════════════
# 业务实体存在性校验
# ═══════════════════════════════════════════════════════════

def validate_entity(
    category: str,
    *,
    user: dict | None = None,
    company_id: int | None = None,
    job_id: int | None = None,
) -> Optional[Result]:
    """校验上传所需的业务实体是否存在。

    参数
    ----
    category   : 上传类别（"resume" / "avatar" / "company_logo" / "company_photo" / "question_bank"）
    user       : 当前登录用户 dict（含 id, role 等）
    company_id : 公司 ID（company_logo / company_photo / question_bank 时需要）
    job_id     : 岗位 ID（question_bank 时需要）

    返回
    ----
    None 表示校验通过，Result 表示校验失败（可直接返回给调用方）。

    注意：此函数只做存在性校验，不做权限校验。权限控制由 API 层的 Depends 负责。
    """
    # ── 用户必须存在 ──
    if user is None:
        return Result.fail(code=401, message="请先登录")

    if not user.get("id"):
        return Result.fail(code=400, message="用户信息不完整")

    # ── 公司校验 ──
    if category in ("company_logo", "company_photo", "question_bank"):
        if not company_id:
            return Result.fail(code=400, message="缺少公司ID")

    # ── 岗位校验 ──
    if category == "question_bank":
        if not job_id:
            return Result.fail(code=400, message="缺少岗位ID")

    return None


def _validate_exists(entity, entity_id: int, entity_type: str) -> Optional[Result]:
    """通用存在性校验：entity 为 None 时返回 404"""
    if not entity:
        return Result.fail(code=404, message=f"{entity_type}不存在: {entity_id}")
    return None


validate_company_exists = functools.partial(_validate_exists, entity_type="公司")
validate_job_exists = functools.partial(_validate_exists, entity_type="岗位")
