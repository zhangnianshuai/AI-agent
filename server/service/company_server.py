import logging
import os
import shutil
import uuid
from pathlib import Path

from server.dao.database import db

_log = logging.getLogger(__name__)
from server.dao.milvus_db import MilvusDataBase
from server.dao.company_dao import CompanyDao
from server.dao.interview_dao import InterviewDao
from server.models.result import Result
from server.utils.snowflake import snowflake
from server.config import settings
from server.utils.permission import AccessControl


class CompanyService:
    """公司业务逻辑"""

    def __init__(self):
        self.company_dao = CompanyDao()
        self.interview_dao = InterviewDao()
        self.access = AccessControl(self.company_dao)

    def create_company(self, user: dict, name: str, short_name: str = None,
                       industry: str = None, scale: str = None,
                       description: str = None, address: str = None,
                       website: str = None, logo_url: str = None,
                       contact_person: str = None, contact_phone: str = None) -> Result:
        """创建公司，仅 hr / admin 角色可操作（API 层已做角色校验）"""
        try:
            user_id = user["id"]

            # 2. 公司重名检查
            exist = self.company_dao.get_company_by_name(name)
            if exist:
                return Result.fail(code=409, message="该公司名称已存在")

            # 3. 生成公司 ID、milvus数据库名、随机题库Collection名
            company_id = snowflake.next_id()
            milvus_db = settings.milvus_db_name
            question_bank_collection = f"col_{uuid.uuid4().hex}"

            # 4. 事务写入：公司表 + 用户-企业关联表（先 MySQL，后 Milvus）
            with db.transaction() as conn:
                self.company_dao.insert_company(
                    conn, company_id, name, short_name, milvus_db,
                    question_bank_collection,
                    industry, scale, description, address, website,
                    logo_url, contact_person, contact_phone
                )
                self.company_dao.insert_user_company(conn, user_id, company_id)

            # 5. MySQL 成功后创建 Milvus 资源（失败不阻塞公司创建）
            try:
                milvus = MilvusDataBase()
                milvus._create_questions_collection(question_bank_collection)
            except Exception as e:
                _log.warning("创建公司后 Milvus collection 创建失败 company_id=%s: %s", company_id, e)

            # 6. 创建公司照片目录
            os.makedirs(self._photo_dir(company_id), exist_ok=True)
            return Result.success(data={
                "company_id": company_id,
                "name": name,
                "milvus_db": milvus_db,
                "question_bank_collection": question_bank_collection,
            })
        except Exception as e:
            return Result.fail(code=500, message=str(e))
    
    def get_public_company_list(self) -> Result:
        """获取公开公司列表（含岗位数量），无需登录"""
        try:
            companies = self.company_dao.get_public_companies()
            return Result.success(data=companies)
        except Exception as e:
            return Result.fail(code=500, message=str(e))

    def get_company_detail(self, company_id: int) -> Result:
        """获取公司详情（所有登录用户可查看）"""
        try:
            company = self.company_dao.get_company_by_id(company_id)
            if not company:
                return Result.fail(code=404, message="公司不存在")
            return Result.success(data=company)
        except Exception as e:
            return Result.fail(code=500, message=str(e))

    def get_company_list(self, user: dict) -> Result:
        """获取用户公司列表，仅 hr / admin 角色可操作（API 层已做角色校验）"""
        try:
            user_id = user["id"]
            role = user["role"]

            # 获取公司列表（管理员看全部，HR只看自己关联的）
            if role == "admin":
                companies = self.company_dao.get_all_companies()
            else:
                companies = self.company_dao.get_company_list_by_userId(user_id)
            return Result.success(data=companies)
        except Exception as e:
            return Result.fail(code=500, message=str(e))

    def update_company(self, company_id: int, user: dict,
                       name: str = None, short_name: str = None,
                       industry: str = None, scale: str = None,
                       description: str = None, address: str = None,
                       website: str = None, logo_url: str = None,
                       contact_person: str = None, contact_phone: str = None) -> Result:
        """修改公司信息，仅该公司 HR / admin 可操作"""
        try:
            user_id = user["id"]
            role = user.get("role")

            company = self.company_dao.get_company_by_id(company_id)
            if not company:
                return Result.fail(code=404, message="公司不存在")

            if err := self.access.can_operate_company(user_id, role, company_id):
                return err

            fields = {k: v for k, v in {
                "name": name, "short_name": short_name,
                "industry": industry, "scale": scale,
                "description": description, "address": address,
                "website": website, "logo_url": logo_url,
                "contact_person": contact_person, "contact_phone": contact_phone,
            }.items() if v is not None}

            if not fields:
                return Result.fail(code=400, message="没有需要更新的字段")

            self.company_dao.update_company(company_id, **fields)
            return Result.success(message="公司信息已更新")
        except Exception as e:
            return Result.fail(code=500, message=str(e))

    def delete_company(self, company_id: int, user: dict) -> Result:
        """删除公司：级联清理所有关联数据 → 删公司 → 删 Milvus → 删照片目录"""
        try:
            user_id = user["id"]
            role = user.get("role")

            company = self.company_dao.get_company_by_id(company_id)
            if not company:
                return Result.fail(code=404, message="公司不存在")

            # 权限：管理员可删任何公司，HR只能删自己关联的公司
            if err := self.access.can_operate_company(user_id, role, company_id):
                return err

            # 检查是否还有岗位
            job_count = self.company_dao.count_jobs_by_company(company_id)
            if job_count > 0:
                return Result.fail(code=400, message=f"该公司下还有{job_count}个岗位，请先删除所有岗位")

            # 1. 事务内级联删除：面试数据 → 岗位（兜底）→ 用户关联 → 公司
            with db.transaction() as conn:
                # 1a. 级联删除该公司下所有面试数据
                interview_result = self.interview_dao.delete_sessions_by_company(company_id, conn)
                _log.info("删除公司级联: company_id=%s interviews=%s", company_id, interview_result)
                # 1b. 兜底删除残留岗位（正常应已为空）
                self.company_dao.delete_jobs_by_company(company_id, conn)
                # 1c. 删除用户-公司关联
                self.company_dao.delete_user_company_by_company(company_id, conn)
                # 1d. 删除公司
                self.company_dao.delete_company(company_id, conn)

            # 2. MySQL 成功后删除 Milvus 题库 Collection（失败仅记录警告）
            collection_name = company.get("question_bank_collection")
            if collection_name:
                try:
                    milvus = MilvusDataBase(collection_name)
                    milvus._delete_question_collection()
                except Exception as e:
                    _log.warning(f"Milvus题库删除失败(company_id={company_id}): {e}")

            # 3. 删除公司照片目录
            try:
                photo_dir = self._photo_dir(company_id)
                if photo_dir.exists():
                    shutil.rmtree(photo_dir)
                    _log.info("公司照片目录已删除: %s", photo_dir)
            except Exception as e:
                _log.warning("公司照片目录删除失败(company_id=%s): %s", company_id, e)

            return Result.success(message="公司已删除")
        except Exception as e:
            return Result.fail(code=500, message=str(e))

    # ── 公司环境照片（纯文件系统，不建表）──────────────────
    _PHOTO_DIR = Path(__file__).resolve().parent.parent / "store" / "company_photo"

    @staticmethod
    def _photo_dir(company_id: int) -> Path:
        return CompanyService._PHOTO_DIR / str(company_id)

    def list_photos(self, company_id: int, user: dict) -> Result:
        """列出公司照片目录下的所有图片 URL"""
        try:
            company = self.company_dao.get_company_by_id(company_id)
            if not company:
                return Result.fail(code=404, message="公司不存在")

            d = self._photo_dir(company_id)
            if not d.exists():
                return Result.success(data=[])

            files = []
            for f in sorted(d.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
                if f.is_file() and f.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
                    files.append({
                        "name": f.name,
                        "url": f"/store/company_photo/{company_id}/{f.name}",
                    })
            return Result.success(data=files)
        except Exception as e:
            return Result.fail(code=500, message=str(e))

    def delete_photo(self, company_id: int, filename: str, user: dict) -> Result:
        """删除公司照片（按文件名）"""
        try:
            user_id = user["id"]

            company = self.company_dao.get_company_by_id(company_id)
            if not company:
                return Result.fail(code=404, message="公司不存在")

            if err := self.access.can_operate_company(user_id, user.get("role"), company_id):
                return err

            # 安全检查：防止路径穿越
            safe_name = os.path.basename(filename)
            filepath = self._photo_dir(company_id) / safe_name
            if not filepath.exists():
                return Result.fail(code=404, message="照片不存在")

            os.remove(filepath)
            return Result.success(message="照片已删除")
        except Exception as e:
            return Result.fail(code=500, message=str(e))