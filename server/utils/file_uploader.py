"""
统一文件上传工具类。

支持的上传类别（UploadCategory）：
  resume        — 用户简历（PDF）
  question_bank — 公司题库（Word）
  avatar        — 用户头像（图片）
  company_logo  — 公司 Logo（图片）

使用方式：
  uploader = FileUploader()
  result = await uploader.upload(file, UploadCategory.AVATAR, user_id=42)
"""

import os
from enum import Enum
from pathlib import Path

from fastapi import UploadFile

from server.models.result import Result
from server.utils.file_validator import (
    read_and_validate_upload,
    validate_entity,
    validate_company_exists,
    validate_job_exists,
    PDF_EXTENSIONS,
    PDF_CONTENT_TYPES,
    WORD_EXTENSIONS,
    WORD_CONTENT_TYPES,
    IMAGE_EXTENSIONS,
    IMAGE_CONTENT_TYPES,
)

# ── 上传类别枚举 ──────────────────────────────────────────
class UploadCategory(str, Enum):
    RESUME = "resume"
    QUESTION_BANK = "question_bank"
    AVATAR = "avatar"
    COMPANY_LOGO = "company_logo"
    COMPANY_PHOTO = "company_photo"

# ── 每个类别的配置：子目录 / 允许格式 / 命名规则 ────────────
_STORE_BASE = Path(__file__).resolve().parent.parent / "store"

CATEGORY_CONFIG = {
    UploadCategory.RESUME: {
        "subdir": "user_resume",
        "extensions": PDF_EXTENSIONS,
        "content_types": PDF_CONTENT_TYPES,
        "name_fn": lambda ext, **kw: f"{kw['user_id']}{ext}",
        "overwrite": True,
    },
    UploadCategory.QUESTION_BANK: {
        "subdir": "job_rag",
        "extensions": WORD_EXTENSIONS,
        "content_types": WORD_CONTENT_TYPES,
        "name_fn": lambda ext, **kw: f"{kw['company_id']}_{kw['job_id']}_{kw['original_filename']}",
        "overwrite": False,
    },
    UploadCategory.AVATAR: {
        "subdir": "user_image",
        "extensions": IMAGE_EXTENSIONS,
        "content_types": IMAGE_CONTENT_TYPES,
        "name_fn": lambda ext, **kw: f"{kw['user_id']}{ext}",
        "overwrite": True,
    },
    UploadCategory.COMPANY_LOGO: {
        "subdir": "company_image",
        "extensions": IMAGE_EXTENSIONS,
        "content_types": IMAGE_CONTENT_TYPES,
        "name_fn": lambda ext, **kw: f"{kw['company_id']}{ext}",
        "overwrite": True,
    },
    UploadCategory.COMPANY_PHOTO: {
        "subdir": "company_photo",
        "extensions": IMAGE_EXTENSIONS,
        "content_types": IMAGE_CONTENT_TYPES,
        # 命名：{company_id}/{uuid}.ext  每个公司最多10张
        "name_fn": lambda ext, **kw: f"{kw['company_id']}/{kw['uuid']}{ext}",
        "overwrite": False,
        "max_count": 10,  # 每个公司最多保留张数，None 表示不限制
    },
}


class FileUploader:
    """统一文件上传器 —— 按类别验证并落盘"""

    # ── 主入口 ──────────────────────────────────────────
    async def upload(
        self,
        file: UploadFile,
        category: UploadCategory,
        **kwargs,
    ) -> Result:
        """上传文件。

        参数
        ----
        file     : FastAPI UploadFile
        category : 上传类别（见 UploadCategory）
        kwargs   : 按类别传递的命名参数，如：
                   resume       → user_id
                   question_bank → company_id, job_id
                   avatar       → user_id
                   company_logo → company_id

        返回
        ----
        Result.success(data={"url": "/store/...", "file_path": "...", "file_name": "..."})
        """
        config = CATEGORY_CONFIG.get(category)
        if not config:
            return Result.fail(code=400, message=f"不支持的上传类别: {category}")

        # 1. 业务实体校验（用户/公司/岗位是否存在）
        user = kwargs.get("user")
        err = validate_entity(
            category.value, user=user,
            company_id=kwargs.get("company_id"),
            job_id=kwargs.get("job_id"),
        )
        if err:
            return err

        company = kwargs.get("company")
        if company is not None:
            err = validate_company_exists(company, kwargs.get("company_id"))
            if err: return err

        job = kwargs.get("job")
        if job is not None:
            err = validate_job_exists(job, kwargs.get("job_id"))
            if err: return err

        # 2. 文件格式校验
        err, file_bytes = await read_and_validate_upload(
            file, config["extensions"], config["content_types"],
        )
        if err:
            return err

        # 3. 目标路径
        target_dir = _STORE_BASE / config["subdir"]
        os.makedirs(target_dir, exist_ok=True)

        ext = Path(file.filename or "file").suffix.lower()
        if ext not in config["extensions"]:
            ext = sorted(config["extensions"])[0]

        # question_bank 需要保留原始文件名
        if category == UploadCategory.QUESTION_BANK:
            kwargs.setdefault("original_filename", file.filename or "upload.docx")

        # company_photo 使用 UUID 命名
        if category == UploadCategory.COMPANY_PHOTO:
            import uuid
            kwargs.setdefault("uuid", uuid.uuid4().hex[:12])

        filename = config["name_fn"](ext, **kwargs)
        filepath = target_dir / filename

        # 4. 数量限制检查
        max_count = config.get("max_count")
        if max_count is not None:
            os.makedirs(filepath.parent, exist_ok=True)
            existing = [f for f in filepath.parent.iterdir() if f.is_file() and f.suffix.lower() in config["extensions"]]
            if len(existing) >= max_count:
                return Result.fail(code=400, message=f"最多上传{max_count}个文件，当前已有{len(existing)}个")

        # 5. 确保父目录存在
        os.makedirs(filepath.parent, exist_ok=True)

        # 6. 是否覆盖
        if not config["overwrite"] and filepath.exists():
            return Result.fail(
                code=409,
                message="文件已经存在",
                data={"file_name": filename, "file_path": str(filepath)},
            )

        # resume: 删除该用户的旧简历文件
        if category == UploadCategory.RESUME:
            self._remove_user_resume_files(target_dir, kwargs["user_id"])

        # 7. 写入
        try:
            filepath.write_bytes(file_bytes)
        except Exception as e:
            return Result.fail(code=500, message=f"文件写入失败: {e}")

        url = f"/store/{config['subdir']}/{filename}"
        return Result.success(data={
            "url": url,
            "file_name": filename,
            "file_path": str(filepath),
        })

    # ── 辅助方法 ────────────────────────────────────────
    @staticmethod
    def _remove_user_resume_files(directory: Path, user_id: int) -> None:
        """删除某个用户的旧简历文件（可能后缀不同）。"""
        prefix = str(user_id)
        for f in directory.iterdir():
            if f.is_file() and f.stem == prefix:
                try:
                    f.unlink()
                except OSError:
                    pass
