from fastapi import APIRouter, Depends
from server.models.request import UpdateRoleRequest, UpdateStatusRequest
from server.models.result import Result
from server.service.admin_server import AdminService
from server.utils.auth import require_role

router = APIRouter(prefix="/admin", tags=["admin"])
service = AdminService()


@router.post("/user/role")
def update_user_role(
    req: UpdateRoleRequest,
    user: dict = Depends(require_role("admin"))
):
    """管理员修改用户角色（candidate / hr ）"""
    return service.update_user_role(
        admin_user_id=user["id"],
        target_user_id=req.user_id,
        new_role=req.role
    )


@router.post("/user/status")
def update_user_status(
    req: UpdateStatusRequest,
    user: dict = Depends(require_role("admin"))
):
    """管理员封禁/解封用户  status: 0=禁用, 1=正常"""
    return service.update_user_status(
        admin_user_id=user["id"],
        target_user_id=req.user_id,
        status=req.status
    )


@router.get("/users")
def list_users(
    role: str = None,
    status: int = None,
    page: int = 1,
    page_size: int = 20,
    user: dict = Depends(require_role("admin"))
):
    """管理员查询用户列表，支持按角色和状态筛选"""
    return service.list_users(role=role, status=status, page=page, page_size=page_size)


@router.get("/agent/traces")
def list_agent_traces(
    limit: int = 100,
    user: dict = Depends(require_role("admin")),
):
    """查看最近 Agent 运行轨迹（仅记录运行元数据，不保存完整 Prompt/候选人回答）。"""
    from server.utils.agent_trace import read_recent_traces

    return Result.success(data={"items": read_recent_traces(limit), "limit": min(max(limit, 1), 500)})
