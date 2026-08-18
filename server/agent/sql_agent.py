"""SqlAgent — 数据库管理助手 Agent.

管理员使用，提供 MySQL / Milvus / MCP 等工具。该类复用 BaseAgent 的历史裁剪与
超时策略，并额外把工具调用作为结构化事件发送给前端。
"""

from __future__ import annotations

import asyncio

from server.agent.base_agent import BaseAgent, STREAM_TIMEOUT
from server.constant import SQL_SYSTEM_PROMPT
from server.utils.agent_trace import AgentTrace


class SqlAgent(BaseAgent):
    def __init__(self, agent_config):
        super().__init__(agent_config)

    def _get_tools(self) -> list:
        from server.agent.agent_tools import admin_tools_list

        return list(admin_tools_list)

    def _build_system_prompt_content(self) -> str:
        return self.agent_config.system_prompt or SQL_SYSTEM_PROMPT

    async def init(self):
        from server.agent.agent_tools.mcp_tools import get_mcp_tools

        mcp_tools = await get_mcp_tools()
        await super().init(extra_tools=mcp_tools if mcp_tools else None)

    async def chat_stream(self, user_message: str):
        """逐事件流式输出 text/tool/end。"""
        self._ensure_ready()
        self._trim_history()
        self.messages["messages"].append({"role": "user", "content": user_message})
        full: list[str] = []
        trace = AgentTrace(
            "sql_agent.stream",
            agent_type=self.__class__.__name__,
            model=self._model_name,
            input_chars=len(user_message),
        )

        try:
            async with asyncio.timeout(STREAM_TIMEOUT):
                async for chunk, metadata in self.app.astream(
                    self.messages,
                    stream_mode="messages",
                ):
                    if metadata.get("langgraph_node") == "tools":
                        tool_name = getattr(chunk, "name", None) or "unknown"
                        trace.event(
                            "tool_result",
                            tool_name=tool_name,
                            result_chars=len(str(getattr(chunk, "content", ""))),
                        )
                        yield {"type": "tool", "name": tool_name}
                        continue

                    content = chunk.content
                    if not content or not isinstance(content, str):
                        continue
                    full.append(content)
                    yield {"type": "text", "content": content}
        except TimeoutError as exc:
            if self.messages["messages"] and self.messages["messages"][-1].get("role") == "user":
                self.messages["messages"].pop()
            trace.finish(status="timeout", error=str(exc), partial_chars=sum(map(len, full)))
            yield {"type": "error", "message": "Agent 调用超时"}
            yield {"type": "end", "full_response": ""}
            return
        except Exception as exc:
            trace.finish(status="error", error=str(exc), partial_chars=sum(map(len, full)))
            raise

        full_text = "".join(full).strip()
        if full_text:
            self.messages["messages"].append({"role": "assistant", "content": full_text})
        trace.finish(output_chars=len(full_text))
        yield {"type": "end", "full_response": full_text}

    async def chat(self, user_message: str) -> str:
        full_text = ""
        async for event in self.chat_stream(user_message):
            if event["type"] == "end":
                full_text = event["full_response"]
        return full_text
