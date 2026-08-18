import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager

# 确保应用日志 INFO 级别以上能输出到控制台
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
    force=True,
)

# 将 server 的父目录加入 path，使得 from server.xxx 导入能正常工作
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

from server.api.user_api import router as user_router
from server.api.resume_api import router as resume_router
from server.api.company_api import router as company_router
from server.api.job_api import router as job_router
from server.api.admin_api import router as admin_router
from server.api.agent_api import router as agent_router
from server.api.interview_api import router as interview_router
from server.api.sql_agent_api import router as sql_agent_router
from server.api.voice_interview_api import router as voice_interview_router
from server.api.file_api import router as file_router

_log = logging.getLogger("server")


# ═══════════════════════════════════════════════════════════
# 应用生命周期（lifespan 替代已弃用的 on_event）
# ═══════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    """管理应用启动/关闭时的资源生命周期"""

    # ── startup ──────────────────────────────────────────
    async def _cleanup_loop(interval: int = 300):
        """每 5 分钟清理超时的 SqlAgent 实例，防止内存泄漏"""
        from server.service.sql_agent_server import sql_agent_service
        while True:
            await asyncio.sleep(interval)
            try:
                await sql_agent_service.cleanup_stale()
            except Exception:
                _log.exception("Agent 清理任务异常")

    cleanup_task = asyncio.create_task(_cleanup_loop())
    _log.info("Agent 超时清理任务已启动（间隔 300s）")

    yield  # ── 应用运行中 ─────────────────────────────────

    # ── shutdown ─────────────────────────────────────────
    # 1. 取消后台清理任务
    cleanup_task.cancel()
    _log.info("Agent 清理任务已取消")

    # 2. 关闭面试服务线程池
    from server.service.interview_server import shutdown_executor
    try:
        shutdown_executor()
        _log.info("面试线程池已关闭")
    except Exception:
        _log.exception("关闭线程池失败")

    # 3. 销毁所有缓存的 SqlAgent
    from server.service.sql_agent_server import sql_agent_service
    try:
        uids = list(sql_agent_service._agents.keys())
        for uid in uids:
            sql_agent_service.destroy_agent(uid)
        _log.info("已销毁 %s 个缓存的 SqlAgent", len(uids))
    except Exception:
        _log.exception("销毁 SqlAgent 失败")


app = FastAPI(lifespan=lifespan)

# 静态文件 — 上传的图片等资源
_STORE_DIR = os.path.join(os.path.dirname(__file__), "store")
os.makedirs(os.path.join(_STORE_DIR, "company_image"), exist_ok=True)
os.makedirs(os.path.join(_STORE_DIR, "user_image"), exist_ok=True)
os.makedirs(os.path.join(_STORE_DIR, "company_photo"), exist_ok=True)
app.mount("/store", StaticFiles(directory=_STORE_DIR), name="store")

app.include_router(file_router)
app.include_router(resume_router)
app.include_router(user_router)
app.include_router(company_router)
app.include_router(job_router)
app.include_router(admin_router)
app.include_router(agent_router)
app.include_router(interview_router)
app.include_router(voice_interview_router)
app.include_router(sql_agent_router)

# CORS —— 允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # 生产环境应限制为前端域名
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)