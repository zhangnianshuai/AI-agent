from server.dao.database import db
from server.utils.sql_builder import build_where

_BASE_FIELDS = """
    SELECT j.id AS job_id, j.title, j.description, j.salary_min, j.salary_max,
           j.location, j.category, j.education_requirement, j.experience_requirement,
           j.headcount, j.status,
           j.company_id, c.name AS company_name, c.industry, c.scale,
           c.logo_url AS company_logo
    FROM job_position j
    LEFT JOIN company c ON j.company_id = c.id
"""

_JOB_FILTER_MAP = {
    "keyword":              "(j.title LIKE %s OR j.description LIKE %s)",
    "location":             "j.location = %s",
    "category":             "j.category = %s",
    "education_requirement": "j.education_requirement = %s",
    "experience_requirement": "j.experience_requirement = %s",
    "company_id":           "j.company_id = %s",
}

class JobDAO:
    """岗位数据访问层 (job_position)"""

    def insert_job(self, job_id: int, company_id: int,
                   question_bank_partition: str,
                   agent_config_id: int = None, title: str = None,
                   description: str = None, salary_min: int = None,
                   salary_max: int = None, location: str = None,
                   category: str = None, education_requirement: str = None,
                   experience_requirement: str = None,
                   headcount: int = 1) -> int:
        """插入岗位"""
        sql = """INSERT INTO job_position
                 (id, company_id, agent_config_id, question_bank_partition,
                  title, description, salary_min, salary_max, location,
                  category, education_requirement, experience_requirement, headcount)
                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
        return db.execute(sql, (
            job_id, company_id, agent_config_id, question_bank_partition,
            title, description, salary_min, salary_max, location,
            category, education_requirement, experience_requirement, headcount
        ))
    
    def delete_job(self, job_id: int) -> int:
        """删除岗位"""
        return db.execute("DELETE FROM job_position WHERE id = %s", (job_id,))

    def get_job_by_id(self, job_id: int) -> dict | None:
        """按ID查询岗位（含公司名）"""
        return db.query(
            "SELECT j.id, j.company_id, j.agent_config_id, j.question_bank_partition,"
            " j.title, j.description, j.salary_min, j.salary_max,"
            " j.location, j.category, j.education_requirement, j.experience_requirement,"
            " j.headcount, j.status, j.created_at, j.updated_at,"
            " c.name AS company_name, c.logo_url AS company_logo"
            " FROM job_position j"
            " LEFT JOIN company c ON j.company_id = c.id"
            " WHERE j.id = %s",
            params=(job_id,), one=True
        )

    def get_jobs_by_company(self, company_id: int) -> list[dict]:
        """查询企业下所有开放岗位"""
        return db.query(
            "SELECT id, company_id, title, description, salary_min, salary_max,"
            " location, category, education_requirement, experience_requirement,"
            " headcount, status, created_at"
            " FROM job_position WHERE company_id = %s AND status = 1",
            params=(company_id,)
        )
    
    def search_jobs(self, page: int = 1, page_size: int = 20,
                    show_all: bool = False, **filters) -> list[dict]:
        """分页搜索岗位（JOIN company）。show_all=True 时不过滤 status"""
        offset = (page - 1) * page_size
        where, params = build_where(filters, _JOB_FILTER_MAP, like_fields={"keyword"})
        if not show_all:
            prefix = "WHERE" if not where else where + " AND"
            where = f"{prefix} j.status = 1"
        sql = (
            f"{_BASE_FIELDS} {where}"
            f" ORDER BY j.created_at DESC"
            f" LIMIT %s OFFSET %s"
        )
        params.extend([page_size, offset])
        return db.query(sql, params=tuple(params))

    def count_jobs(self, show_all: bool = False, **filters) -> int:
        """统计符合条件的岗位总数。show_all=True 时不过滤 status"""
        where, params = build_where(filters, _JOB_FILTER_MAP, like_fields={"keyword"})
        if not show_all:
            prefix = "WHERE" if not where else where + " AND"
            where = f"{prefix} j.status = 1"
        sql = f"SELECT COUNT(*) AS total FROM job_position j {where}"
        result = db.query(sql, params=tuple(params), one=True)
        return result["total"] if result else 0
    
    def agent_config_id(self, job_id: int) -> int | None:
        """查询岗位绑定的 Agent 配置 ID，未绑定或岗位不存在返回 None"""
        row = db.query(
            "SELECT agent_config_id FROM job_position WHERE id = %s",
            params=(job_id,), one=True
        )
        if row is None:
            return None
        return row["agent_config_id"]

    def update_agent_config_id(self, job_id: int, agent_config_id: int, conn=None) -> int:
        """更新岗位绑定的 Agent 配置 ID

        conn: 可选，传入则使用该连接执行（不提交），否则走 db.execute()
        """
        sql = "UPDATE job_position SET agent_config_id = %s WHERE id = %s"
        if conn is not None:
            with conn.cursor() as cursor:
                return cursor.execute(sql, (agent_config_id, job_id))
        return db.execute(sql, (agent_config_id, job_id))

    def refuse_job(self, job_id: int) -> int:
        """拒绝岗位"""
        return db.execute("UPDATE job_position SET status = 2 WHERE id = %s",
                          (job_id,))
    
    def get_job_list_by_ids(self, job_ids: list[int]) -> list[dict]:
        """按ID列表查询岗位（含公司名）"""
        if not job_ids:
            return []
        return db.query(
            "SELECT j.id AS job_id, j.title, c.name AS company_name,"
            "       c.logo_url AS company_logo,"
            "       j.salary_min, j.salary_max,"
            "       j.education_requirement, j.experience_requirement"
            " FROM job_position j"
            " LEFT JOIN company c ON j.company_id = c.id"
            " WHERE j.id IN %s",
            params=(tuple(job_ids),)
        )

    def get_question_bank_collection_and_partition(self, company_id: int, job_id: int) -> tuple:
        """获取企业题库集合(company表)和岗位分区(job_position表)"""
        # 1. 查 company 表取 question_bank_collection（Milvus 集合名）
        company = db.query(
            "SELECT question_bank_collection FROM company WHERE id = %s",
            params=(company_id,), one=True,
        )
        if not company:
            raise ValueError("公司不存在")
        # 2. 查 job_position 表取 question_bank_partition（分区键）
        job = db.query(
            "SELECT question_bank_partition FROM job_position WHERE id = %s",
            params=(job_id,), one=True,
        )
        if not job:
            raise ValueError("岗位不存在")
        return company["question_bank_collection"], job["question_bank_partition"]
        
