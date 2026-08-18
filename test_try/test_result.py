import json
import unittest

from server.models.result import Result


class ResultTests(unittest.TestCase):
    def test_success_accepts_message_and_data(self):
        response = Result.success(message="密码更新成功", data={"id": 1})

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.body.decode("utf-8"))
        self.assertEqual(payload["code"], 200)
        self.assertEqual(payload["message"], "密码更新成功")
        self.assertEqual(payload["data"], {"id": 1})


if __name__ == "__main__":
    unittest.main()
