import json
import sys
import types
import unittest
from unittest.mock import MagicMock, Mock

fake_config = types.ModuleType("server.config")
fake_config.settings = Mock()
fake_config.llm = Mock()
sys.modules["server.config"] = fake_config

fake_database = types.ModuleType("server.dao.database")
fake_database.db = Mock()
sys.modules["server.dao.database"] = fake_database

fake_ai_server = types.ModuleType("server.service.ai_server")
fake_ai_server.LLMService = Mock
sys.modules["server.service.ai_server"] = fake_ai_server

from server.models.request import ResumeUpdateRequest
from server.service.resume_server import ResumeService


class ResumeUpdateTests(unittest.TestCase):
    def setUp(self):
        self.service = ResumeService.__new__(ResumeService)
        self.service.dao = Mock()
        self.service.llm = Mock()
        self.service.db = MagicMock()
        self.conn = MagicMock()
        self.service.db.transaction.return_value.__enter__.return_value = self.conn

        self.request = ResumeUpdateRequest(
            name="张三",
            age=25,
            sex="男",
            work_year="3年",
            skills="Python, FastAPI",
            self_evaluation="沟通良好",
            job_intention="后端开发",
            education=[{
                "school_name": "某某大学",
                "degree": "本科",
                "major": "计算机科学与技术",
                "start_date": "2019-09",
                "end_date": "2023-06",
            }],
            projects=[{
                "project_name": "招聘系统",
                "description": "负责后端开发",
                "role": "后端开发",
                "start_date": "2025-01",
                "end_date": "2025-06",
            }],
        )

    def test_update_requires_an_existing_saved_resume(self):
        self.service.dao.get_resume_by_id.return_value = None

        result = self.service.update_resume(1, self.request)

        self.assertEqual(result.status_code, 404)
        payload = json.loads(result.body.decode("utf-8"))
        self.assertEqual(payload["message"], "请先保存简历后再进行修改")
        self.service.llm.get_user_image.assert_not_called()
        self.service.dao.update_resume.assert_not_called()

    def test_update_preserves_resume_id_and_returns_updated_resume(self):
        updated = {"id": 99, "user_id": 1, "name": "张三", "age": 25}
        self.service.dao.get_resume_by_id.side_effect = [
            {"id": 99, "user_id": 1},
            updated,
        ]
        self.service.llm.get_user_image.return_value = "候选人技术画像"

        result = self.service.update_resume(1, self.request)

        self.assertEqual(result.status_code, 200)
        payload = json.loads(result.body.decode("utf-8"))
        self.assertEqual(payload["message"], "简历修改成功")
        self.assertEqual(payload["data"], updated)
        update_args = self.service.dao.update_resume.call_args.args
        self.assertEqual(update_args[1], 99)
        self.assertEqual(update_args[2], 1)
        self.service.dao.delete_resume_details.assert_called_once_with(self.conn, 99)
        self.service.dao.insert_education.assert_called_once()
        self.service.dao.insert_project.assert_called_once()


if __name__ == "__main__":
    unittest.main()
