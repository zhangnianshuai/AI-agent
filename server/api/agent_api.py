from fastapi import APIRouter, Depends, Query
from server.service.agent_server import AgentService
from server.models.agent import agent_config
from server.utils.auth import require_role

router = APIRouter(prefix="/agent", tags=["agent"])
service = AgentService()


@router.post("/config/setup")
def setup_config(config: agent_config, job_id: int = Query(0),
                 config_id: int | None = Query(None),
                 user: dict = Depends(require_role("hr", "admin"))):
    """创建或更新 Agent 面试官配置并绑定到岗位"""
    return service.set_up_agent_config(job_id, config, config_id, user=user)


@router.get("/config/{config_id}")
def get_config(config_id: int, user: dict = Depends(require_role("admin"))):
    """按 ID 查询 Agent 配置"""
    return service.get_config(config_id)


@router.get("/configs")
def list_configs(user: dict = Depends(require_role("hr", "admin"))):
    """查询全部 Agent 配置（HR 仅返回自己公司的）"""
    return service.list_configs(user=user)
