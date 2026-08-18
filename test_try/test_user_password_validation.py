import json
import unittest
from unittest.mock import Mock

import bcrypt

from server.service.user_server import UserService


class UserServicePasswordValidationTests(unittest.TestCase):
    def test_update_password_rejects_password_not_matching_registration_rules(self):
        service = UserService.__new__(UserService)
        service.user_dao = Mock()
        service.user_dao.get_user_by_id.return_value = {
            "id": 1,
            "username": "testuser",
            "password_hash": bcrypt.hashpw(b"oldpassword", bcrypt.gensalt()).decode("utf-8"),
        }

        result = service.update_password(1, "oldpassword", "abcdef")

        self.assertEqual(result.status_code, 400)
        payload = json.loads(result.body.decode("utf-8"))
        self.assertEqual(payload["message"], "密码必须同时包含英文字母、数字和符号")
        service.user_dao.update_password.assert_not_called()


if __name__ == "__main__":
    unittest.main()
