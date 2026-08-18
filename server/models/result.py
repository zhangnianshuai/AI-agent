from fastapi.responses import JSONResponse

import json
from datetime import date, datetime
from decimal import Decimal


def _json_serializer(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Type {type(obj)} not serializable")


class Result(JSONResponse):
    def __init__(self, code: int = 500, message: str = None, data: dict = None):
        self.code = code
        self.message = message
        self.data = data
        # 用 code 字段作为真正的 HTTP 状态码
        super().__init__(
            content={"code": code, "message": message, "data": data},
            status_code=code,          # ← 关键：HTTP 状态码跟着业务 code 走
        )

    @classmethod
    def success(cls, data: dict = None, message: str = None):
        return cls(code=200, message=message, data=data)

    @classmethod
    def fail(cls, code: int = 500, message: str = None, data: dict = None):
        return cls(code=code, message=message, data=data)

    @classmethod
    def ws_msg(cls, code: int = 200, message: str = None, data: dict = None) -> str:
        """WebSocket 统一消息格式，返回 JSON 字符串（与 HTTP 响应结构一致）"""
        return json.dumps(
            {"code": code, "message": message, "data": data},
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            default=_json_serializer,
        )

    def render(self, content=None) -> bytes:
        """重写渲染方法，处理 datetime 序列化"""
        if content is None:
            content = {}
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            default=_json_serializer,
        ).encode("utf-8")
