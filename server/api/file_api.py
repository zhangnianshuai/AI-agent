"""
统一文件上传 API —— 一个端点处理所有上传类别。

POST /file/upload
  - category: "resume" | "question_bank" | "avatar" | "company_logo" | "company_photo"
  - file: 上传的文件
  - company_id (可选，company_logo / company_photo / question_bank 时需要)
  - job_id (可选，question_bank 时需要)

校验链路（由 FileUploader 统一执行）：
  validate_entity → read_and_validate_upload → max_count → 落盘
"""

from fastapi import APIRouter, Depends, UploadFile, File, Form

from server.dao.company_dao import CompanyDao
from server.dao.job_dao import JobDAO
from server.models.result import Result
from server.utils.auth import get_current_user, require_role
from server.utils.file_uploader import FileUploader, UploadCategory

router = APIRouter(prefix="/file", tags=["file"])
uploader = FileUploader()
_company_dao = CompanyDao()
_job_dao = JobDAO()


@router.post("/upload")
async def upload_file(
    category: UploadCategory = Form(...),
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
    company_id: int = Form(None),
    job_id: int = Form(None),
):
    """统一文件上传入口。

    按 category 自动选择校验规则与存储路径：
    - resume        → store/user_resume/{user_id}.pdf
    - question_bank → store/job_rag/{company_id}_{job_id}_{filename}
    - avatar        → store/user_image/{user_id}.png
    - company_logo  → store/company_image/{company_id}.png
    - company_photo → store/company_photo/{company_id}/{uuid}.png (≤10)
    """
    kwargs = {"user": user, "user_id": user["id"]}

    if company_id is not None:
        kwargs["company_id"] = company_id
        company = _company_dao.get_company_by_id(company_id)
        kwargs["company"] = company  # 可能为 None，由 validator 判 404

    if job_id is not None:
        kwargs["job_id"] = job_id
        job = _job_dao.get_job_by_id(job_id)
        kwargs["job"] = job  # 可能为 None，由 validator 判 404

    return await uploader.upload(file, category, **kwargs)
