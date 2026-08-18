from fastapi import APIRouter, Depends
from server.models.request import CompanyCreateRequest
from server.service.company_server import CompanyService
from server.utils.auth import require_role, get_current_user

router = APIRouter(prefix="/company", tags=["company"])
service = CompanyService()


@router.post("/create")
def create_company(req: CompanyCreateRequest,user: dict = Depends(require_role("hr", "admin"))):
    return service.create_company(
        user=user,
        name=req.name,
        short_name=req.short_name,
        industry=req.industry,
        scale=req.scale,
        description=req.description,
        address=req.address,
        website=req.website,
        logo_url=req.logo_url,
        contact_person=req.contact_person,
        contact_phone=req.contact_phone,
    )

@router.get("/public/list")
def get_public_company_list():
    """获取公开公司列表（含岗位数量），无需登录"""
    return service.get_public_company_list()


@router.get("/list")
def get_company_list(user: dict = Depends(require_role("hr", "admin"))):
    return service.get_company_list(user)


@router.get("/{company_id}/detail")
def get_company_detail(company_id: int, user: dict = Depends(get_current_user)):
    """获取公司详情（所有登录用户可查看）"""
    return service.get_company_detail(company_id)


@router.put("/{company_id}")
def update_company(company_id: int, req: CompanyCreateRequest, user: dict = Depends(require_role("hr", "admin"))):
    """修改公司信息"""
    return service.update_company(
        company_id=company_id, user=user,
        name=req.name, short_name=req.short_name,
        industry=req.industry, scale=req.scale,
        description=req.description, address=req.address,
        website=req.website, logo_url=req.logo_url,
        contact_person=req.contact_person, contact_phone=req.contact_phone,
    )


@router.delete("/{company_id}")
def delete_company(company_id: int, user: dict = Depends(require_role("hr", "admin"))):
    """删除公司：先删Milvus题库 → 删MySQL公司+用户关联（前提：公司下无岗位）"""
    return service.delete_company(company_id, user)


# ── 公司环境照片 ──────────────────────────────────────────

@router.get("/{company_id}/photos")
def list_photos(company_id: int, user: dict = Depends(get_current_user)):
    """获取公司照片列表"""
    return service.list_photos(company_id, user)


@router.delete("/{company_id}/photos/{filename:path}")
def delete_photo(company_id: int, filename: str, user: dict = Depends(require_role("hr", "admin"))):
    """删除公司照片（按文件名）"""
    return service.delete_photo(company_id, filename, user)