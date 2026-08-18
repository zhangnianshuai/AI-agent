from server.dao.database import db

class ResumeDao:

    def insert_resume(self, conn, resume_id: int, user_id: int, name: str, age: int,
                  sex: str, work_year: str, skills: str, self_evaluation: str,
                  parsed_content: str, job_intention: str,
                  file_name: str, file_url: str) -> int:
        sql = """INSERT INTO resume (id, user_id, name, age, sex, work_year,
                skills, self_evaluation, parsed_content, job_intention, file_name, file_url)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
        with conn.cursor() as cursor:
            return cursor.execute(sql, (resume_id, user_id, name, age, sex, work_year,
                                        skills, self_evaluation, parsed_content, job_intention,file_name,file_url))
        
    def insert_education(self, conn, edu_id, user_id, resume_id, school_name, degree, major, start_date, end_date):
        sql = """INSERT INTO education (id, user_id, resume_id, school_name, degree, major, start_date, end_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"""
        with conn.cursor() as cursor:
            return cursor.execute(sql, (edu_id, user_id, resume_id, school_name, degree, major, start_date, end_date))

    def insert_project(self, conn, proj_id, resume_id, project_name, description,
                   role, start_date, end_date):
        sql = """INSERT INTO personal_project (id, resume_id, project_name, description, role, start_date, end_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s)"""
        with conn.cursor() as cursor:
            return cursor.execute(sql, (proj_id, resume_id, project_name, description,
                                        role, start_date, end_date))

    def update_resume(self, conn, resume_id: int, user_id: int, name: str, age: int,
                      sex: str, work_year: str, skills: str, self_evaluation: str,
                      parsed_content: str, job_intention: str) -> int:
        """原地更新简历主表，保留 resume_id 及原文件信息。"""
        sql = """UPDATE resume
                 SET name = %s, age = %s, sex = %s, work_year = %s,
                     skills = %s, self_evaluation = %s,
                     parsed_content = %s, job_intention = %s
                 WHERE id = %s AND user_id = %s"""
        with conn.cursor() as cursor:
            return cursor.execute(sql, (
                name, age, sex, work_year, skills, self_evaluation,
                parsed_content, job_intention, resume_id, user_id,
            ))

    def delete_resume_details(self, conn, resume_id: int):
        """删除旧的教育与项目明细，供事务内按提交内容重新写入。"""
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM education WHERE resume_id = %s", (resume_id,))
            cursor.execute("DELETE FROM personal_project WHERE resume_id = %s", (resume_id,))

        
    def delete_resume_by_user_id(self, conn, user_id: int):
        """删除用户所有简历（含教育经历和项目经历），在事务内执行"""
        with conn.cursor() as cursor:
            # 1. 查所有简历 ID（用同一个 conn，保证事务一致性）
            cursor.execute("SELECT id FROM resume WHERE user_id = %s", (user_id,))
            rows = cursor.fetchall()
            if not rows:
                return
            resume_ids = [row["id"] for row in rows]

            # 2. 批量删除关联表
            cursor.executemany("DELETE FROM education WHERE resume_id = %s",
                            [(rid,) for rid in resume_ids])
            cursor.executemany("DELETE FROM personal_project WHERE resume_id = %s",
                            [(rid,) for rid in resume_ids])
            cursor.executemany("DELETE FROM resume WHERE id = %s",
                            [(rid,) for rid in resume_ids])

    def get_resume_by_id(self, user_id: int) -> dict | None:
        """按 user_id 查询简历（含教育经历和项目经历，并行查询减少延迟）"""
        resume = db.query(
            "SELECT id, user_id, name, age, sex, work_year, skills,"
            "       self_evaluation, parsed_content, job_intention,"
            "       file_name, file_url"
            " FROM resume WHERE user_id = %s ORDER BY created_at DESC LIMIT 1",
            params=(user_id,), one=True
        )
        if not resume:
            return None

        resume_id = resume["id"]

        resume["education"] = db.query(
            "SELECT id, school_name, degree, major, start_date, end_date"
            " FROM education WHERE resume_id = %s",
            params=(resume_id,),
        )
        resume["projects"] = db.query(
            "SELECT id, project_name, description, role, start_date, end_date"
            " FROM personal_project WHERE resume_id = %s",
            params=(resume_id,),
        )

        return resume

    def get_resume_file(self, user_id: int) -> dict | None:
        return db.query(
            "SELECT file_name, file_url FROM resume WHERE user_id = %s AND file_url IS NOT NULL AND file_url != ''",
            params=(user_id,), one=True
        )
    
    def get_parsed_content(self, user_id: int) -> dict | None:
        return db.query(
            "SELECT parsed_content FROM resume WHERE user_id = %s",
            params=(user_id,), one=True
        )



