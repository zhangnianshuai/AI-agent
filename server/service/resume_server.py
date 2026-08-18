import os
import json
import pdfplumber
from server.config import settings,llm
from server.dao.resume_dao import ResumeDao
from server.models.result import Result
from server.utils.snowflake import snowflake
from server.service.ai_server import LLMService
from server.dao.database import db
from server.models.request import ResumeUpdateRequest

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "store", "user_resume")



class ResumeService:

    def __init__(self):
        self.dao = ResumeDao()
        self.llm = LLMService(llm)
        self.db = db

    def _find_resume_file(self, user_id: int) -> tuple[str, str] | None:
        """在文件夹中查找属于该用户的简历文件，返回 (filepath, filename) 或 None"""
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        for f in os.listdir(UPLOAD_DIR):
            name, ext = os.path.splitext(f)
            if name == str(user_id):
                return os.path.join(UPLOAD_DIR, f), f
        return None

    def parse_resume(self, user_id: int) -> Result:
        try:
            # 1. 去文件夹查找有没有user_id名字的简历，有就开始解析
            result = self._find_resume_file(user_id)
            if not result:
                return Result.fail(code=400, message="请先上传简历")

            filepath, filename = result

            # 2. 提取文本
            with pdfplumber.open(filepath) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)

            if not text.strip():
                return Result.fail(code=400, message="请确认简历是否上传,格式是否为pdf")

            # 3. 调大模型解析
            content = self.llm.analysis_resume(text)
            content["file_url"] = filepath
            content["file_name"] = filename
            return Result.success(data=content)

        except json.JSONDecodeError:
            return Result.fail(code=500, message="大模型返回格式异常，请重试")
        except Exception as e:
            return Result.fail(code=500, message=str(e))

    def _user_image_prompt(self, name, skills, self_evaluation, job_intention,
                           education, projects, work_year, sex) -> str:
        """拼装 LLM 用户画像的提示文本"""
        return (
            f"姓名：{name}，技能：{skills}，个人评价：{self_evaluation},"
            f"求职意向：{job_intention},教育经历：{education},项目经历：{projects},"
            f"工作年限：{work_year},性别：{sex}"
        )

    def _insert_edu_and_proj(self, conn, user_id, resume_id, education, projects):
        """事务内批量插入教育经历和项目经历"""
        for edu in education:
            self.dao.insert_education(conn,
                snowflake.next_id(), user_id, resume_id,
                edu.get("school_name", ""), edu.get("degree", ""),
                edu.get("major", ""), edu.get("start_date", ""), edu.get("end_date", ""),
            )
        for proj in projects:
            self.dao.insert_project(conn, snowflake.next_id(), resume_id,
                project_name=proj.get("project_name", ""),
                description=proj.get("description", ""),
                role=proj.get("role", ""),
                start_date=proj.get("start_date", ""),
                end_date=proj.get("end_date", ""),
            )

    def upload_resume(self, file_name, file_url, user_id: int, name, age, sex,
                      work_year, skills, self_evaluation, job_intention,
                      education, projects) -> Result:
        try:
            prompt = self._user_image_prompt(
                name, skills, self_evaluation, job_intention,
                education, projects, work_year, sex,
            )
            parsed_content = self.llm.get_user_image(prompt)
            resume_id = snowflake.next_id()

            with self.db.transaction() as conn:
                self.dao.delete_resume_by_user_id(conn, user_id)
                self.dao.insert_resume(conn,
                    resume_id, user_id, name, age, sex, work_year, skills,
                    self_evaluation, parsed_content, job_intention, file_name, file_url,
                )
                self._insert_edu_and_proj(conn, user_id, resume_id, education, projects)

            return Result.success(data={"resume_id": resume_id})
        except Exception as e:
            return Result.fail(code=500, message=str(e))
        
    def get_resume(self, user_id: int) -> Result:
        try:
            resume = self.dao.get_resume_by_id(user_id)
            if not resume:
                return Result.fail(code=404, message="简历不存在")
            return Result.success(data=resume)
        except Exception as e:
            return Result.fail(code=500, message=str(e))

    def update_resume(self, user_id: int, req: ResumeUpdateRequest) -> Result:
        """更新当前用户已保存的简历，并返回更新后的完整简历。"""
        try:
            existing = self.dao.get_resume_by_id(user_id)
            if not existing:
                return Result.fail(code=404, message="请先保存简历后再进行修改")

            education = [item.model_dump() for item in req.education]
            projects = [item.model_dump() for item in req.projects]
            prompt = self._user_image_prompt(
                req.name, req.skills, req.self_evaluation, req.job_intention,
                education, projects, req.work_year, req.sex,
            )
            parsed_content = self.llm.get_user_image(prompt)

            resume_id = existing["id"]
            with self.db.transaction() as conn:
                self.dao.update_resume(
                    conn, resume_id, user_id, req.name, req.age, req.sex,
                    req.work_year, req.skills, req.self_evaluation,
                    parsed_content, req.job_intention,
                )
                self.dao.delete_resume_details(conn, resume_id)
                self._insert_edu_and_proj(conn, user_id, resume_id, education, projects)

            updated = self.dao.get_resume_by_id(user_id)
            return Result.success(message="简历修改成功", data=updated)
        except Exception as e:
            return Result.fail(code=500, message=str(e))
        
    def delete_file(self, user_id: int) -> Result:
        """删除用户的简历PDF文件"""
        try:
            result = self._find_resume_file(user_id)
            if not result:
                return Result.fail(code=404, message="未找到简历文件")
            filepath, filename = result
            os.remove(filepath)
            return Result.success(data={"file_name": filename})
        except Exception as e:
            return Result.fail(code=500, message=str(e))




