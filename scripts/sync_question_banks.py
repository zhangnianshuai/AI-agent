"""
手动初始化公司题库集合：扫描 company 表 → 检查/创建 Milvus 题库 collection。

用法：
    cd AI-agent
    python scripts/sync_question_banks.py

选项：
    --dry-run      仅扫描，不实际创建
    --company-id ID 仅处理指定公司
"""

import argparse
import logging
import os
import sys
import uuid

# 确保 from server.xxx 导入能正常工作
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from server.config import settings, milvus_client
from server.dao.database import db
from server.dao.milvus_db import MilvusDataBase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
    force=True,
)
_log = logging.getLogger("sync_question_banks")


def query_companies(company_id: int | None = None) -> list[dict]:
    """查询待处理的公司的 id, name, question_bank_collection"""
    if company_id:
        return db.query(
            "SELECT id, name, question_bank_collection FROM company WHERE id = %s",
            params=(company_id,),
        )
    return db.query(
        "SELECT id, name, question_bank_collection FROM company"
    )


def sync_question_banks(company_id: int | None = None, dry_run: bool = False):
    """核心逻辑：确保每家公司都有对应的 Milvus 题库集合"""
    companies = query_companies(company_id)
    if not companies:
        _log.warning("未找到公司")
        return

    _log.info("共 %d 家公司待处理", len(companies))

    mdb = MilvusDataBase()  # 使用默认名，仅用于调用 _create_questions_collection
    created = 0
    skipped = 0
    failed = 0

    for i, c in enumerate(companies, 1):
        cid = c["id"]
        cname = c.get("name", "N/A")
        existing_col = c.get("question_bank_collection")

        _log.info("[%d/%d] %s (id=%s)", i, len(companies), cname, cid)

        try:
            if existing_col:
                # 已有 collection 名 → 检查 Milvus 中是否存在
                if milvus_client.has_collection(existing_col):
                    _log.info("  ↳ 题库集合已存在: %s，跳过", existing_col)
                    skipped += 1
                    continue
                else:
                    # 记录中有但 Milvus 中不存在 → 重建
                    _log.info("  ↳ 集合 %s 在 Milvus 中不存在，重新创建", existing_col)
                    collection_name = existing_col
            else:
                # 无记录 → 生成新集合名
                collection_name = f"col_{uuid.uuid4().hex}"
                _log.info("  ↳ 无题库集合，新建: %s", collection_name)

            if dry_run:
                _log.info("  ↳ [DRY-RUN] 将创建集合 %s", collection_name)
                created += 1
            else:
                mdb._create_questions_collection(collection_name)
                _log.info("  ↳ 集合 %s 已创建", collection_name)

                # 更新 company 表
                if not existing_col:
                    db.execute(
                        "UPDATE company SET question_bank_collection = %s WHERE id = %s",
                        (collection_name, cid),
                    )
                    _log.info("  ↳ company 表已更新")
                created += 1

        except Exception as e:
            _log.warning("  ↳ 失败: %s", e)
            failed += 1

    # 汇总
    summary = (
        f"\n{'=' * 50}\n"
        f"同步完成: 成功 {created}, 跳过 {skipped}, 失败 {failed} / 总计 {len(companies)}"
    )
    if dry_run:
        summary += "\n[DRY-RUN 模式，未实际创建]"
    _log.info(summary)


def main():
    parser = argparse.ArgumentParser(description="手动初始化公司题库 Milvus 集合")
    parser.add_argument("--dry-run", action="store_true", help="仅扫描预览，不实际创建")
    parser.add_argument("--company-id", type=int, default=None, help="仅处理指定公司 ID")
    args = parser.parse_args()

    _log.info("=" * 50)
    _log.info("公司题库集合初始化工具")
    _log.info("  Milvus: %s:%s / %s", settings.milvus_host, settings.milvus_port, settings.milvus_db_name)
    if args.dry_run:
        _log.info("  *** DRY-RUN 模式 ***")
    _log.info("=" * 50)

    sync_question_banks(company_id=args.company_id, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
