from fastapi import APIRouter, Depends
from server.models.request import JobCreateRequest, JobSearchRequest, QuestionCreateRequest, QuestionGetRequest, QuestionUpdateRequest, QuestionDeleteRequest
from server.service.job_server import JobService
from server.utils.auth import get_current_user, require_role, get_optional_user
router = APIRouter(prefix="/job", tags=["job"])

service = JobService()


@router.post("/create")
def create_job(req: JobCreateRequest,user: dict=Depends(require_role("hr","admin"))):
    return service.create_job(
        user_id=user["id"],
        role=user.get("role"),
        company_id=req.company_id,
        title=req.title,
        agent_config_id=req.agent_config_id,
        description=req.description,
        salary_min=req.salary_min,
        salary_max=req.salary_max,
        location=req.location,
        category=req.category,
        education_requirement=req.education_requirement,
        experience_requirement=req.experience_requirement,
        headcount=req.headcount,
    )

@router.post("/search")
def search_jobs(req: JobSearchRequest, user: dict = Depends(get_optional_user)):
    """分页条件搜索岗位（所有筛选参数可选，不传即全量分页）
    -- 普通用户/游客只看上架岗位，HR/管理员看全部"""
    role = user.get("role") if user else None
    return service.search_jobs(req, role)

@router.get("/ai_search")
def ai_search_jobs(user: dict=Depends(get_current_user)):
    """根据AI模型推荐岗位,一次最多只会返回10个"""
    return service.ai_search_jobs(user["id"])

@router.get("/detail/{job_id}")
def get_job_detail(job_id: int, user: dict = Depends(get_optional_user)):
    """获取岗位详情。普通用户只能看已上架，HR/admin可看全部"""
    role = user.get("role") if user else None
    return service.get_job_detail(job_id, role)

@router.post("/insert_question")
def insert_question(req: QuestionCreateRequest, user: dict = Depends(require_role("hr", "admin"))):
    """插入题目"""
    return service.insert_question(req.company_id, req.job_id, user["id"], user.get("role"))

@router.get("/get_question")
def get_question(req: QuestionGetRequest = Depends(), user: dict = Depends(require_role("hr", "admin"))):
    """分页获取岗位题库"""
    return service.get_question(req.company_id, req.job_id, user["id"],
                                page=req.page, page_size=req.page_size, role=user.get("role"))


@router.put("/update_question")
def update_question(req: QuestionUpdateRequest, user: dict = Depends(require_role("hr", "admin"))):
    """修改单道题目（通过主键 pk）"""
    return service.update_question(
        company_id=req.company_id,
        pk=req.pk,
        user_id=user["id"],
        question=req.question,
        answer=req.answer,
        scoring_criteria=req.scoring_criteria,
        difficulty=req.difficulty,
        role=user.get("role"),
    )


@router.delete("/delete_question")
def delete_question(req: QuestionDeleteRequest, user: dict = Depends(require_role("hr", "admin"))):
    """删除单道题目（通过主键 pk）"""
    return service.delete_question(req.company_id, req.pk, user["id"], user.get("role"))


@router.put("/update/{job_id}")
def update_job(job_id: int, req: JobCreateRequest, user: dict = Depends(require_role("hr", "admin"))):
    """更新岗位信息"""
    return service.update_job(
        job_id=job_id,
        user_id=user["id"],
        role=user.get("role"),
        title=req.title,
        description=req.description,
        salary_min=req.salary_min,
        salary_max=req.salary_max,
        location=req.location,
        category=req.category,
        education_requirement=req.education_requirement,
        experience_requirement=req.experience_requirement,
        headcount=req.headcount,
    )


@router.put("/online/{job_id}")
def online_job(job_id: int, user: dict = Depends(require_role("hr", "admin"))):
    """上架岗位（设置状态为1）"""
    return service.set_job_status(job_id, user["id"], 1, user.get("role"))


@router.put("/offline/{job_id}")
def offline_job(job_id: int, user: dict = Depends(require_role("hr", "admin"))):
    """下架岗位（设置状态为2）"""
    return service.set_job_status(job_id, user["id"], 2, user.get("role"))


@router.delete("/{job_id}")
def delete_job(job_id: int, user: dict = Depends(require_role("hr", "admin"))):
    """删除岗位：先清Milvus题库+画像，再删MySQL数据"""
    return service.delete_job_cascade(job_id, user["id"], user.get("role"))

