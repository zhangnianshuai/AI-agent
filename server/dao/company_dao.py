from server.dao.database import db
from server.utils.sql_builder import build_set


class CompanyDao:
    """公司数据访问层 (company)"""

    def insert_company(self, conn, company_id: int, name: str, short_name: str = None,
                       milvus_db: str = None, question_bank_collection: str = None,
                       industry: str = None, scale: str = None,
                       description: str = None, address: str = None, website: str = None,
                       logo_url: str = None, contact_person: str = None,
                       contact_phone: str = None) -> int:
        """在事务中插入公司"""
        sql = """INSERT INTO company
                 (id, name, short_name, milvus_db, question_bank_collection,
                  industry, scale, description, address, website,
                  logo_url, contact_person, contact_phone)
                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
        with conn.cursor() as cursor:
            return cursor.execute(sql, (
                company_id, name, short_name, milvus_db, question_bank_collection,
                industry, scale, description, address, website,
                logo_url, contact_person, contact_phone
            ))

    def insert_user_company(self, conn, user_id: int, company_id: int) -> int:
        """在事务中将创建者关联到公司"""
        sql = "INSERT INTO user_company (user_id, company_id) VALUES (%s, %s)"
        with conn.cursor() as cursor:
            return cursor.execute(sql, (user_id, company_id))

    def get_company_by_name(self, name: str) -> dict | None:
        """按公司全称查询（用于查重）"""
        return db.query(
            "SELECT id, name, short_name, milvus_db, question_bank_collection,"
            " industry, scale, description, address, website, logo_url,"
            " contact_person, contact_phone, status, created_at, updated_at"
            " FROM company WHERE name = %s",
            params=(name,), one=True
        )

    def get_company_by_id(self, company_id: int) -> dict | None:
        """按ID查询公司"""
        return db.query(
            "SELECT id, name, short_name, milvus_db, question_bank_collection,"
            " industry, scale, description, address, website, logo_url,"
            " contact_person, contact_phone, status, created_at, updated_at"
            " FROM company WHERE id = %s",
            params=(company_id,), one=True
        )
    
    def check_user_in_company(self, user_id: int, company_id: int) -> bool:
        """检查用户是否属于该公司"""
        result = db.query(
            "SELECT 1 FROM user_company WHERE user_id = %s AND company_id = %s",
            params=(user_id, company_id), one=True
        )
        return result is not None

    def get_company_list_by_userId(self, user_id: int) -> list:
        """按用户ID查询关联的公司列表（通过user_company关联表）"""
        return db.query(
            """SELECT c.id, c.name, c.short_name, c.industry, c.scale,
                      c.address, c.website, c.logo_url,
                      c.contact_person, c.contact_phone, c.status
               FROM user_company uc
               INNER JOIN company c ON uc.company_id = c.id
               WHERE uc.user_id = %s""",
            params=(user_id,)
        )

    def get_all_companies(self) -> list:
        """获取所有公司列表"""
        return db.query(
            "SELECT id, name, short_name, industry, scale, address, website, logo_url, contact_person, contact_phone, status FROM company ORDER BY id DESC"
        )

    def get_public_companies(self) -> list:
        """获取所有公司（含岗位数量），公开接口用"""
        return db.query(
            """SELECT c.id, c.name, c.short_name, c.industry, c.scale,
                      c.address, c.website, c.logo_url, c.description,
                      (SELECT COUNT(*) FROM job_position j WHERE j.company_id = c.id) AS job_count
               FROM company c
               WHERE c.status = 1
               ORDER BY c.id DESC"""
        )

    def count_jobs_by_company(self, company_id: int) -> int:
        """统计公司下岗位数量"""
        row = db.query(
            "SELECT COUNT(*) AS cnt FROM job_position WHERE company_id = %s",
            params=(company_id,), one=True
        )
        return row["cnt"] if row else 0

    def delete_company(self, company_id: int, conn=None) -> int:
        """删除公司"""
        if conn:
            with conn.cursor() as cursor:
                return cursor.execute("DELETE FROM company WHERE id = %s", (company_id,))
        return db.execute("DELETE FROM company WHERE id = %s", (company_id,))

    def delete_user_company_by_company(self, company_id: int, conn=None) -> int:
        """解除所有用户与公司的关联"""
        if conn:
            with conn.cursor() as cursor:
                return cursor.execute("DELETE FROM user_company WHERE company_id = %s", (company_id,))
        return db.execute("DELETE FROM user_company WHERE company_id = %s", (company_id,))

    def update_company(self, company_id: int, **fields) -> int:
        """动态更新公司字段。返回影响行数"""
        sets, params = build_set(**fields)
        if not sets:
            return 0
        params.append(company_id)
        return db.execute(f"UPDATE company SET {sets} WHERE id = %s", tuple(params))

    def delete_jobs_by_company(self, company_id: int, conn=None) -> int:
        """删除公司下所有岗位"""
        if conn:
            with conn.cursor() as cursor:
                return cursor.execute("DELETE FROM job_position WHERE company_id = %s", (company_id,))
        return db.execute("DELETE FROM job_position WHERE company_id = %s", (company_id,))
