from fastapi import APIRouter, Depends
from server.models.request import ResumeUploadRequest, ResumeUpdateRequest
from server.service.resume_server import ResumeService
from server.utils.auth import get_current_user

router = APIRouter(prefix="/resume", tags=["resume"])
service = ResumeService()

@router.delete("/deleteFile")
async def delete_file(user: dict = Depends(get_current_user)):
    return service.delete_file(user["id"])

@router.get("/load")
async def load_resume(user: dict = Depends(get_current_user)):
    return service.parse_resume(user["id"])

@router.post("/upload")
def upload_resume(req: ResumeUploadRequest, user: dict = Depends(get_current_user)):
    return service.upload_resume(req.file_name, req.file_url,
        user["id"], req.name, req.age, req.sex,
        req.work_year, req.skills, req.self_evaluation,
        req.job_intention,req.education, req.projects
    )

@router.get("/getResume")
async def get_resume( user: dict = Depends(get_current_user)):
    return service.get_resume(user["id"])


@router.put("/update")
def update_resume(req: ResumeUpdateRequest, user: dict = Depends(get_current_user)):
    """修改当前用户已经保存过的简历，并返回修改后的完整内容。"""
    return service.update_resume(user["id"], req)





