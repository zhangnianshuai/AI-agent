"""
外部 MCP 工具 — 供 SQL Agent 调用远程服务

通过 langchain_mcp_adapters 将 MCP Server 的工具转为 LangChain 工具。
"""

import os
import logging

from langchain_mcp_adapters.client import MultiServerMCPClient

_log = logging.getLogger(__name__)

_ip = os.environ.get("server_ip", "127.0.0.1")

_mcp_client = MultiServerMCPClient({
    "weather_mcp": {
        "url": f"http://{_ip}:8089/mcp",
        "transport": "streamable_http",
    },
})


async def get_mcp_tools() -> list:
    """异步获取 MCP 工具列表（LangChain Tool 格式），首次调用时连接远端。

    返回空列表表示 MCP 服务不可用（不阻塞 Agent 初始化）。
    """
    try:
        return await _mcp_client.get_tools()
    except Exception as e:
        _log.warning(f"MCP 工具加载失败（weather_mcp @ {_ip}:8089）: {e}")
        return []
