"""BaseAgent — 通用 Agent 基类。

提取 LLM 创建、ReAct Agent 初始化、消息管理、超时控制和流式对话等通用能力。
"""

from __future__ import annotations

import asyncio

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from server.config import settings
from server.utils.agent_trace import AgentTrace

STREAM_TIMEOUT = 120
MAX_HISTORY_CHARS = 32000


class BaseAgent:
    def __init__(self, agent_config):
        self.agent_config = agent_config
        self.app = None
        self.messages: dict = {"messages": []}

    def close(self):
        self.app = None
        self.messages = {"messages": []}

    @property
    def _model_name(self) -> str:
        return self.agent_config.model_name or settings.openai_model

    def _make_llm(
        self,
        streaming: bool,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ChatOpenAI:
        return ChatOpenAI(
            model=self._model_name,
            api_key=settings.openai_api_key,
            base_url=settings.base_url,
            temperature=(
                temperature if temperature is not None else self.agent_config.temperature
            ),
            max_tokens=max_tokens or self.agent_config.max_tokens,
            streaming=streaming,
        )

    def _get_tools(self) -> list:
        raise NotImplementedError("子类必须实现 _get_tools()")

    def _build_system_prompt_content(self) -> str:
        raise NotImplementedError("子类必须实现 _build_system_prompt_content()")

    async def init(self, extra_tools: list | None = None):
        llm = self._make_llm(streaming=True)
        tools = list(self._get_tools())
        if extra_tools:
            tools.extend(extra_tools)
        self.app = create_react_agent(model=llm, tools=tools)
        self.messages["messages"] = [
            {"role": "system", "content": self._build_system_prompt_content()}
        ]

    def _ensure_ready(self):
        if self.app is None:
            raise RuntimeError("Agent 尚未初始化，请先调用 init()")

    @staticmethod
    def _content_len(message: dict) -> int:
        content = message.get("content", "")
        if isinstance(content, str):
            return len(content)
        return len(str(content))

    def _trim_history(self):
        """截断历史，但始终保留首个 system prompt 和最近上下文。"""
        msgs = self.messages.get("messages", [])
        if len(msgs) <= 3:
            return
        if sum(self._content_len(m) for m in msgs) <= MAX_HISTORY_CHARS:
            return

        system = msgs[:1]
        recent = msgs[1:]
        kept: list[dict] = []
        char_budget = MAX_HISTORY_CHARS - sum(self._content_len(m) for m in system)
        used = 0
        for message in reversed(recent):
            size = self._content_len(message)
            if kept and used + size > char_budget:
                break
            kept.append(message)
            used += size
        self.messages["messages"] = system + list(reversed(kept))

    async def chat(self, user_message: str) -> str:
        self._ensure_ready()
        self._trim_history()
        self.messages["messages"].append({"role": "user", "content": user_message})
        trace = AgentTrace(
            "agent.chat",
            agent_type=self.__class__.__name__,
            model=self._model_name,
            input_chars=len(user_message),
        )

        try:
            async with asyncio.timeout(STREAM_TIMEOUT):
                result = await self.app.ainvoke(self.messages)
        except TimeoutError as exc:
            if self.messages["messages"] and self.messages["messages"][-1].get("role") == "user":
                self.messages["messages"].pop()
            trace.finish(status="timeout", error=str(exc))
            raise asyncio.TimeoutError("Agent 调用超时") from exc
        except Exception as exc:
            trace.finish(status="error", error=str(exc))
            raise

        reply = result["messages"][-1].content
        self.messages["messages"].append({"role": "assistant", "content": reply})
        trace.finish(output_chars=len(reply or ""))
        return reply

    async def chat_stream(self, user_message: str):
        """流式对话。

        Yields:
            (content, False): 普通 token/chunk
            (full_text, True): 完整回复
        """
        self._ensure_ready()
        self._trim_history()
        self.messages["messages"].append({"role": "user", "content": user_message})
        full: list[str] = []
        trace = AgentTrace(
            "agent.stream",
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
                        trace.event(
                            "tool_result",
                            tool_name=getattr(chunk, "name", None) or "unknown",
                            result_chars=len(str(getattr(chunk, "content", ""))),
                        )
                        continue
                    content = chunk.content
                    if not content or not isinstance(content, str):
                        continue
                    full.append(content)
                    yield content, False
        except TimeoutError as exc:
            if self.messages["messages"] and self.messages["messages"][-1].get("role") == "user":
                self.messages["messages"].pop()
            trace.finish(status="timeout", error=str(exc), partial_chars=sum(map(len, full)))
            full_text = "（AI响应超时，请稍后重试）"
            yield full_text, True
            return
        except Exception as exc:
            trace.finish(status="error", error=str(exc), partial_chars=sum(map(len, full)))
            raise

        full_text = "".join(full).strip()
        if full_text:
            self.messages["messages"].append({"role": "assistant", "content": full_text})
        trace.finish(output_chars=len(full_text))
        yield full_text, True
