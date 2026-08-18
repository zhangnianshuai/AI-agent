"""面试三表 interview_session / interview_record / interview_evaluation 的数据访问层"""

from server.dao.database import db
from server.models.agent import InterviewEvaluation, InterviewRecord, InterviewSession
from server.utils.sql_builder import build_set, build_where


class InterviewDao:
    """面试三表数据访问"""

    # === interview_session ===
    def create_session(self, session: InterviewSession) -> int:
        sql = """INSERT INTO interview_session
                 (id, user_id, job_position_id, agent_config_id, resume_id,
                  company_id, status, start_time)
                 VALUES (%s,%s,%s,%s,%s,%s,%s,%s)"""
        return db.execute(sql, (
            session.id, session.user_id, session.job_position_id,
            session.agent_config_id, session.resume_id,
            session.company_id, session.status.value if hasattr(session.status, 'value') else session.status,
            session.start_time
        ))

    def update_session(self, session_id: int, **fields):
        """更新 session 字段（status, end_time, duration 等）"""
        sets, params = build_set(**fields)
        if not sets:
            return 0
        params.append(session_id)
        return db.execute(f"UPDATE interview_session SET {sets} WHERE id = %s", tuple(params))

    def get_session_by_id(self, session_id: int) -> dict | None:
        return db.query(
            "SELECT id, user_id, job_position_id, agent_config_id, resume_id,"
            " company_id, status, start_time, end_time, duration, created_at, updated_at"
            " FROM interview_session WHERE id = %s",
            params=(session_id,), one=True)

    def list_recent_sessions(self, user_id: int = None, page: int = 1,
                             page_size: int = 20) -> list[dict]:
        """分页返回面试会话摘要，含岗位名称和公司名称。user_id 为 None 时查全部"""
        offset = (page - 1) * page_size
        where = "WHERE s.user_id = %s" if user_id else ""
        params = [page_size, offset]
        if user_id:
            params.insert(0, user_id)
        return db.query(
            "SELECT s.id, s.user_id, s.job_position_id, s.company_id,"
            "       s.status, s.start_time, s.end_time,"
            "       j.title AS job_title,"
            "       c.name AS company_name"
            " FROM interview_session s"
            " LEFT JOIN job_position j ON s.job_position_id = j.id"
            " LEFT JOIN company c ON s.company_id = c.id"
            f" {where}"
            " ORDER BY s.created_at DESC"
            " LIMIT %s OFFSET %s",
            params=tuple(params),
        )

    def count_sessions(self, user_id: int = None) -> int:
        """统计面试会话总数。user_id 为 None 时查全部"""
        if user_id:
            row = db.query(
                "SELECT COUNT(*) AS total FROM interview_session WHERE user_id = %s",
                params=(user_id,), one=True,
            )
        else:
            row = db.query(
                "SELECT COUNT(*) AS total FROM interview_session", one=True,
            )
        return row["total"] if row else 0

    # === interview_record ===
    def create_record(self, record: InterviewRecord) -> int:
        sql = """INSERT INTO interview_record
                 (id, session_id, round_number, question_type, question, answer, score, comment, duration)
                 VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
        return db.execute(sql, (
            record.id, record.session_id, record.round_number,
            record.question_type, record.question, record.answer,
            record.score, record.comment, record.duration
        ))

    def get_records_by_session(self, session_id: int) -> list[dict]:
        return db.query(
            "SELECT id, session_id, round_number, question_type, question,"
            " answer, score, comment, duration, created_at"
            " FROM interview_record WHERE session_id = %s ORDER BY round_number",
            params=(session_id,)
        )

    def update_record(self, record: InterviewRecord) -> int:
        """更新一条问答记录的评分、点评、题型"""
        sql = """UPDATE interview_record
                 SET score = %s, comment = %s, question_type = %s
                 WHERE id = %s"""
        return db.execute(sql, (
            record.score, record.comment, record.question_type, record.id
        ))

    # === interview_evaluation ===
    def create_evaluation(self, eval: InterviewEvaluation) -> int:
        sql = """INSERT INTO interview_evaluation
                 (id, session_id, total_score, summary, strengths, weaknesses, suggestion, is_pass)
                 VALUES (%s,%s,%s,%s,%s,%s,%s,%s)"""
        return db.execute(sql, (
            eval.id, eval.session_id, eval.total_score, eval.summary,
            eval.strengths, eval.weaknesses, eval.suggestion,
            1 if eval.is_pass is True else 0
        ))

    # === 级联删除 ===
    def delete_session_cascade(self, session_id: int, conn=None) -> dict:
        """级联删除：records → evaluation → session，返回各表删除行数"""
        result = {}
        if conn:
            with conn.cursor() as c:
                c.execute("DELETE FROM interview_record WHERE session_id = %s", (session_id,))
                result['records'] = c.rowcount
                c.execute("DELETE FROM interview_evaluation WHERE session_id = %s", (session_id,))
                result['evaluation'] = c.rowcount
                c.execute("DELETE FROM interview_session WHERE id = %s", (session_id,))
                result['session'] = c.rowcount
        else:
            result['records'] = db.execute("DELETE FROM interview_record WHERE session_id = %s", (session_id,))
            result['evaluation'] = db.execute("DELETE FROM interview_evaluation WHERE session_id = %s", (session_id,))
            result['session'] = db.execute("DELETE FROM interview_session WHERE id = %s", (session_id,))
        return result

    def delete_sessions_by_company(self, company_id: int, conn=None) -> dict:
        """级联删除某公司下所有面试数据：records → evaluations → sessions"""
        result = {}
        if conn:
            with conn.cursor() as c:
                c.execute(
                    "DELETE ir FROM interview_record ir "
                    "INNER JOIN interview_session s ON ir.session_id = s.id "
                    "WHERE s.company_id = %s", (company_id,))
                result['records'] = c.rowcount
                c.execute(
                    "DELETE ie FROM interview_evaluation ie "
                    "INNER JOIN interview_session s ON ie.session_id = s.id "
                    "WHERE s.company_id = %s", (company_id,))
                result['evaluations'] = c.rowcount
                c.execute("DELETE FROM interview_session WHERE company_id = %s", (company_id,))
                result['sessions'] = c.rowcount
        else:
            # 非事务模式：先删子表再删主表
            result['records'] = db.execute(
                "DELETE ir FROM interview_record ir "
                "INNER JOIN interview_session s ON ir.session_id = s.id "
                "WHERE s.company_id = %s", (company_id,))
            result['evaluations'] = db.execute(
                "DELETE ie FROM interview_evaluation ie "
                "INNER JOIN interview_session s ON ie.session_id = s.id "
                "WHERE s.company_id = %s", (company_id,))
            result['sessions'] = db.execute(
                "DELETE FROM interview_session WHERE company_id = %s", (company_id,))
        return result

    def delete_sessions_by_job(self, job_id: int, conn=None) -> dict:
        """级联删除某岗位下所有面试数据：records → evaluations → sessions"""
        result = {}
        if conn:
            with conn.cursor() as c:
                c.execute(
                    "DELETE ir FROM interview_record ir "
                    "INNER JOIN interview_session s ON ir.session_id = s.id "
                    "WHERE s.job_position_id = %s", (job_id,))
                result['records'] = c.rowcount
                c.execute(
                    "DELETE ie FROM interview_evaluation ie "
                    "INNER JOIN interview_session s ON ie.session_id = s.id "
                    "WHERE s.job_position_id = %s", (job_id,))
                result['evaluations'] = c.rowcount
                c.execute("DELETE FROM interview_session WHERE job_position_id = %s", (job_id,))
                result['sessions'] = c.rowcount
        else:
            result['records'] = db.execute(
                "DELETE ir FROM interview_record ir "
                "INNER JOIN interview_session s ON ir.session_id = s.id "
                "WHERE s.job_position_id = %s", (job_id,))
            result['evaluations'] = db.execute(
                "DELETE ie FROM interview_evaluation ie "
                "INNER JOIN interview_session s ON ie.session_id = s.id "
                "WHERE s.job_position_id = %s", (job_id,))
            result['sessions'] = db.execute(
                "DELETE FROM interview_session WHERE job_position_id = %s", (job_id,))
        return result

    # === 组合查询（面试报告） ===
    def get_full_report(self, session_id: int) -> dict | None:
        session = self.get_session_by_id(session_id)
        if not session:
            return None
        return {
            "session": session,
            "records": self.get_records_by_session(session_id),
            "evaluation": db.query(
                "SELECT id, session_id, total_score, summary, strengths,"
                " weaknesses, suggestion, is_pass, created_at, updated_at"
                " FROM interview_evaluation WHERE session_id = %s",
                params=(session_id,), one=True
            )
        }

    # === 候选人管理 ===

    _CANDIDATE_FILTER_MAP = {
        "is_pass":      "e.is_pass = %s",
        "job_title":    "jp.title LIKE %s",
        "job_location": "jp.location = %s",
    }

    def list_company_candidates(self, company_id: int, page: int = 1,
                                page_size: int = 20, **filters) -> list[dict]:
        """分页查询公司下所有面试候选人（含用户信息、岗位信息、评价结果）"""
        offset = (page - 1) * page_size
        where, params = build_where(
            filters, self._CANDIDATE_FILTER_MAP,
            like_fields={"job_title"},
            prefix="WHERE",
        )
        params.insert(0, company_id)
        if not where or where == "WHERE ":
            where = "WHERE s.company_id = %s"
        else:
            where = where.replace("WHERE ", "WHERE s.company_id = %s AND ", 1)
        params.extend([page_size, offset])
        return db.query(
            "SELECT u.id AS user_id, u.real_name, u.email, u.phone,"
            "       jp.title AS job_title, jp.location AS job_location,"
            "       s.id AS session_id, s.status AS session_status,"
            "       e.is_pass, e.total_score"
            " FROM interview_session s"
            " JOIN user u ON s.user_id = u.id"
            " JOIN job_position jp ON s.job_position_id = jp.id"
            " LEFT JOIN interview_evaluation e ON s.id = e.session_id"
            f" {where}"
            " ORDER BY s.created_at DESC"
            " LIMIT %s OFFSET %s",
            params=tuple(params),
        )

    def count_company_candidates(self, company_id: int, **filters) -> int:
        """统计公司下候选人总数"""
        where, params = build_where(
            filters, self._CANDIDATE_FILTER_MAP,
            like_fields={"job_title"},
            prefix="WHERE",
        )
        params.insert(0, company_id)
        if not where or where == "WHERE ":
            where = "WHERE s.company_id = %s"
        else:
            where = where.replace("WHERE ", "WHERE s.company_id = %s AND ", 1)
        row = db.query(
            "SELECT COUNT(DISTINCT s.id) AS total"
            " FROM interview_session s"
            " JOIN user u ON s.user_id = u.id"
            " JOIN job_position jp ON s.job_position_id = jp.id"
            " LEFT JOIN interview_evaluation e ON s.id = e.session_id"
            f" {where}",
            params=tuple(params), one=True,
        )
        return row["total"] if row else 0

    def update_evaluation_pass(self, session_id: int, is_pass: int) -> int:
        """更新或插入面试评价的通过状态。返回影响行数"""
        exist = db.query(
            "SELECT id FROM interview_evaluation WHERE session_id = %s",
            params=(session_id,), one=True,
        )
        if exist:
            return db.execute(
                "UPDATE interview_evaluation SET is_pass = %s WHERE session_id = %s",
                (is_pass, session_id),
            )
        return db.execute(
            "INSERT INTO interview_evaluation (session_id, is_pass) VALUES (%s, %s)",
            (session_id, is_pass),
        )
