"""
LLM 回复工具 — 从 LLM 回复中提取 JSON + 调用重试。
"""

import asyncio
import json
import logging
import re
import time
from functools import wraps

_log = logging.getLogger(__name__)

# 重试默认配置
DEFAULT_RETRIES = 3
DEFAULT_RETRY_DELAY = 1.5  # 秒


def retry_on_failure(max_retries: int = DEFAULT_RETRIES,
                     delay: float = DEFAULT_RETRY_DELAY,
                     exceptions: tuple = (Exception,)):
    """LLM 调用同步重试装饰器（指数退避）"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt < max_retries:
                        wait = delay * (2 ** (attempt - 1))
                        _log.warning(
                            "%s 第 %s/%s 次失败: %s，%ss后重试...",
                            func.__name__, attempt, max_retries, e, wait,
                        )
                        time.sleep(wait)
            _log.error("%s 重试 %s 次全部失败: %s", func.__name__, max_retries, last_exc)
            raise last_exc
        return wrapper
    return decorator


async def async_retry_ainvoke(
    llm, messages,
    max_retries: int = DEFAULT_RETRIES,
    delay: float = DEFAULT_RETRY_DELAY,
):
    """异步调用 LLM.ainvoke，带指数退避重试（供 Agent 直接使用）

    Args:
        llm: LangChain LLM 实例（或其 ainvoke 方法）
        messages: 消息列表
        max_retries: 最大重试次数
        delay: 初始延迟（秒），每次翻倍

    Returns:
        LLM 响应对象

    Raises:
        最后一次异常（所有重试耗尽后）
    """
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            return await llm.ainvoke(messages)
        except Exception as e:
            last_exc = e
            if attempt < max_retries:
                wait = delay * (2 ** (attempt - 1))
                _log.warning(
                    "LLM.ainvoke 第 %s/%s 次失败: %s，%ss后重试...",
                    attempt, max_retries, e, wait,
                )
                await asyncio.sleep(wait)
    _log.error("LLM.ainvoke 重试 %s 次全部失败: %s", max_retries, last_exc)
    raise last_exc


def extract_json_from_reply(reply: str) -> dict:
    """从 LLM 回复中提取 JSON 对象。

    处理常见的大模型输出格式：
    - ```json ... ``` 代码块包裹
    - ``` ... ``` 无语言标注的代码块
    - 纯文本中嵌入的 JSON 对象

    Args:
        reply: LLM 返回的原始文本

    Returns:
        解析后的 dict。解析失败返回空 dict。
    """
    # 1. 去除 markdown 代码块标记
    content = re.sub(r'```\w*\s*', '', reply)
    content = re.sub(r'```\s*', '', content)
    # 2. 截取第一个 { 到最后一个 } 之间的内容
    start = content.find('{')
    end = content.rfind('}')
    if start == -1 or end == -1:
        return {}
    content = content[start:end + 1]

    # 3. 解析 JSON（使用 raw_decode 处理尾部多余字符）
    try:
        decoder = json.JSONDecoder()
        return decoder.raw_decode(content.strip())[0]
    except (json.JSONDecodeError, ValueError):
        return {}
