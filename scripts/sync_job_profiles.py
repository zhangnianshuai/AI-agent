"""
手动同步岗位画像：读取 MySQL job_position 表 → LLM 生成画像 → 存入 Milvus。

用法：
    cd AI-agent
    python scripts/sync_job_profiles.py

选项：
    --force     强制全量重建（即使 Milvus 已有数据也重新生成）
    --dry-run   仅扫描，不实际写入 Milvus
    --job-id ID 仅同步指定岗位
"""

import argparse
import logging
import os
import sys

# 确保 from server.xxx 导入能正常工作
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from server.config import settings, llm
from server.dao.database import db
from server.dao.milvus_db import MilvusDataBase
from server.models.milvus import JobProfileInput
from server.service.ai_server import LLMService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
    force=True,
)
_log = logging.getLogger("sync_job_profiles")


def query_jobs(job_id: int | None = None, include_all: bool = False) -> list[dict]:
    """查询待同步的岗位。默认查所有开放岗位，传 job_id 则只查指定岗位。"""
    if job_id:
        sql = (
            "SELECT j.id AS job_id, j.company_id, j.title, j.description, "
            "j.location, j.category, j.education_requirement, j.experience_requirement "
            "FROM job_position j WHERE j.id = %s"
        )
        return db.query(sql, params=(job_id,))
    else:
        if include_all:
            sql = (
                "SELECT j.id AS job_id, j.company_id, j.title, j.description, "
                "j.location, j.category, j.education_requirement, j.experience_requirement "
                "FROM job_position j"
            )
        else:
            sql = (
                "SELECT j.id AS job_id, j.company_id, j.title, j.description, "
                "j.location, j.category, j.education_requirement, j.experience_requirement "
                "FROM job_position j WHERE j.status = 1"
            )
        return db.query(sql)


def build_profile_text(job: dict) -> str:
    """拼接岗位字段为一段自然语言，供 LLM 生成画像"""
    parts = [f"job_id: {job['job_id']}"]
    if job.get("title"):
        parts.append(f"岗位名称: {job['title']}")
    if job.get("description"):
        parts.append(f"岗位描述和要求: {job['description']}")
    if job.get("location"):
        parts.append(f"工作地点: {job['location']}")
    if job.get("category"):
        parts.append(f"岗位类型: {job['category']}")
    if job.get("education_requirement"):
        parts.append(f"学历要求: {job['education_requirement']}")
    if job.get("experience_requirement"):
        parts.append(f"工作经验要求: {job['experience_requirement']}")
    return ", ".join(parts)


def sync_profiles(job_id: int | None = None, force: bool = False, dry_run: bool = False,
                  include_all: bool = False):
    """核心同步逻辑"""
    mdb = MilvusDataBase(settings.collection_name)

    # 1. 确保 collection 存在
    mdb._ensure_collection(lambda: mdb._create_job_profile_collection(mdb._collection_name))
    _log.info("集合 %s 已就绪", mdb._collection_name)

    # 2. 检查是否已有数据（非 force 模式）
    if not force:
        try:
            result = mdb._milvus.query(
                collection_name=mdb._collection_name,
                filter="job_id >= 0",
                output_fields=["job_id"],
                limit=1,
            )
            if result and not job_id:
                _log.info("Milvus 中已有画像数据，跳过同步。使用 --force 强制重建")
                return
        except Exception:
            pass  # collection 刚创建，继续同步

    # 3. 查询岗位
    jobs = query_jobs(job_id, include_all=include_all)
    if not jobs:
        _log.warning("未找到待同步的岗位")
        return

    # 4. 同步
    _log.info("共 %d 个岗位待处理", len(jobs))
    ai_server = LLMService(llm)
    synced = 0
    skipped = 0
    failed = 0

    for i, job in enumerate(jobs, 1):
        jid = job["job_id"]
        title = job.get("title", "N/A")
        _log.info("[%d/%d] 处理岗位: %s (id=%s)", i, len(jobs), title, jid)

        try:
            # 拼接 → LLM 生成画像
            text = build_profile_text(job)
            profile_text = ai_server.get_job_profile(text)
            if not profile_text:
                _log.warning("  ↳ LLM 返回空结果，跳过")
                skipped += 1
                continue

            _log.debug("  ↳ 画像: %s", profile_text[:80])

            if dry_run:
                _log.info("  ↳ [DRY-RUN] 将写入 %d 字画像", len(profile_text))
                synced += 1
            else:
                profile = JobProfileInput(
                    job_id=jid,
                    profile_text=profile_text,
                    company_id=job.get("company_id", 0),
                )
                mdb._insert_job_profile(profile)
                synced += 1
                _log.info("  ↳ 已写入 Milvus")
        except Exception as e:
            _log.warning("  ↳ 失败: %s", e)
            failed += 1

    # 5. 汇总
    summary = f"\n{'='*50}\n同步完成: 成功 {synced}, 跳过 {skipped}, 失败 {failed} / 总计 {len(jobs)}"
    if dry_run:
        summary += "\n[DRY-RUN 模式，未实际写入]"
    _log.info(summary)


def main():
    parser = argparse.ArgumentParser(description="手动同步岗位画像到 Milvus")
    parser.add_argument("--force", action="store_true", help="强制全量重建，忽略已有数据")
    parser.add_argument("--dry-run", action="store_true", help="仅扫描预览，不实际写入")
    parser.add_argument("--job-id", type=int, default=None, help="仅同步指定岗位 ID")
    parser.add_argument("--all", action="store_true", help="同步所有岗位（含已关闭的）")
    args = parser.parse_args()

    _log.info("=" * 50)
    _log.info("岗位画像同步工具")
    _log.info("  Milvus: %s:%s / %s", settings.milvus_host, settings.milvus_port, settings.collection_name)
    _log.info("  LLM:   %s", settings.openai_model)
    if args.dry_run:
        _log.info("  *** DRY-RUN 模式 ***")
    _log.info("=" * 50)

    sync_profiles(job_id=args.job_id, force=args.force, dry_run=args.dry_run,
                  include_all=args.all)


if __name__ == "__main__":
    main()
