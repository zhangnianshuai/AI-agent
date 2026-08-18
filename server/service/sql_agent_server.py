"""
SqlAgentService — SQL Admin Agent 服务

负责：
  - 获取或创建 sql_admin 类型的 agent_config
  - 按用户 ID 缓存 Agent 实例，页面刷新/重连时复用
  - 自动清理超时会话（默认 30 分钟无活动）
"""

import time
import asyncio
import logging

from server.dao.agent_dao import AgentConfigDao
from server.models.agent import agent_config, AgentType

_log = logging.getLogger("agent.sql_admin")

# Agent 空闲超时（秒），超时后自动销毁
_IDLE_TIMEOUT = 30 * 60  # 30 分钟


class SqlAgentService:
    def __init__(self):
        self.config_dao = AgentConfigDao()
        # ── Agent 缓存：{user_id: {"agent": SqlAgent, "last_access": timestamp}} ──
        self._agents: dict[int, dict] = {}
        self._lock = asyncio.Lock()

    # ── config ──────────────────────────────────────────────

    def get_or_create_config(self) -> agent_config:
        """查找已有的 sql_admin 配置，不存在则新建一个默认配置"""
        cfgs = self.config_dao.list_configs()
        for c in cfgs:
            if getattr(c, "type", None) == AgentType.sql_admin:
                return c

        config = agent_config(
            type=AgentType.sql_admin,
            model_name="deepseek-v4-flash",
            temperature=0.30,
            max_tokens=4096,
            system_prompt=None,
        )
        self.config_dao.create_config(config)
        return config

    # ── Agent 缓存管理 ──────────────────────────────────────

    async def get_or_create_agent(self, user_id: int):
        """获取或创建该用户的 Agent 实例。

        如果已有缓存的 Agent（如页面刷新后重连），直接复用，保留对话历史。
        否则创建新 Agent 并缓存。
        """
        from server.agent.sql_agent import SqlAgent

        # 先清理超时 Agent，防止长时间运行的进程中僵尸积累
        await self.cleanup_stale()

        async with self._lock:
            entry = self._agents.get(user_id)

            if entry is not None:
                # 检查 agent 是否还活着（app 未被 close）
                agent = entry["agent"]
                if agent.app is not None:
                    entry["last_access"] = time.time()
                    _log.debug("复用 Agent 缓存 user=%s messages=%s", user_id,
                              len(agent.messages.get("messages", [])))
                    return agent
                # app 为 None 说明被 close 了，移除重建
                del self._agents[user_id]
                _log.debug("Agent 已失效，重新创建 user=%s", user_id)

            # ── 新建 Agent ──
            config = self.get_or_create_config()
            agent = SqlAgent(config)
            await agent.init()
            self._agents[user_id] = {
                "agent": agent,
                "last_access": time.time(),
            }
            _log.debug("创建新 Agent user=%s", user_id)
            return agent

    def touch(self, user_id: int):
        """更新最后访问时间（每次对话后调用）"""
        entry = self._agents.get(user_id)
        if entry:
            entry["last_access"] = time.time()

    async def cleanup_stale(self):
        """清理超时的 Agent 实例（可被定时任务或新连接时触发）"""
        async with self._lock:
            now = time.time()
            stale = [
                uid for uid, entry in self._agents.items()
                if now - entry["last_access"] > _IDLE_TIMEOUT
            ]
            for uid in stale:
                entry = self._agents.pop(uid)
                entry["agent"].close()
                _log.info("清理超时 Agent user=%s", uid)

    def destroy_agent(self, user_id: int):
        """主动销毁指定用户的 Agent"""
        entry = self._agents.pop(user_id, None)
        if entry:
            entry["agent"].close()
            _log.debug("主动销毁 Agent user=%s", user_id)

    def get_messages(self, user_id: int) -> list[dict] | None:
        """获取指定用户 Agent 的消息历史（用于前端恢复渲染）。

        Returns:
            消息列表（不含 system prompt），无活跃 Agent 返回 None
        """
        entry = self._agents.get(user_id)
        if not entry or entry["agent"].app is None:
            return None
        msgs = entry["agent"].messages.get("messages", [])
        # 过滤 system prompt，只返回对话消息
        return [m for m in msgs if m.get("role") != "system"]

    def clear_messages(self, user_id: int) -> bool:
        """仅清空消息历史，保留 Agent 实例（下次对话从空白开始）。

        Returns:
            True 表示成功，False 表示无活跃 Agent
        """
        entry = self._agents.get(user_id)
        if not entry or entry["agent"].app is None:
            return False
        # 保留 system prompt，清空对话
        agent = entry["agent"]
        sys_msg = [m for m in agent.messages.get("messages", []) if m.get("role") == "system"]
        agent.messages["messages"] = sys_msg
        entry["last_access"] = time.time()
        _log.debug("清空消息 user=%s", user_id)
        return True

    @property
    def active_count(self) -> int:
        return len(self._agents)


# 模块级单例（由 main.py / sql_agent_api.py 共享）
sql_agent_service = SqlAgentService()
