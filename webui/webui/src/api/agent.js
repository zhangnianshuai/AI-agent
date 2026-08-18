import api from './index'

export function setupAgentConfig(jobId, configId, data) {
  return api.post('/agent/config/setup', data, { params: { job_id: jobId, config_id: configId } })
}

export function getAgentConfig(configId) {
  return api.get(`/agent/config/${configId}`)
}

export function listAgentConfigs() {
  return api.get('/agent/configs')
}

// ── SQL Agent 会话管理 ──

/** 查询当前用户 SQL Agent 会话状态 */
export function getSqlAgentStatus() {
  return api.get('/agent/sql/status')
}

/** 获取对话历史消息（用于恢复渲染） */
export function getSqlAgentMessages() {
  return api.get('/agent/sql/messages')
}

/** 仅清空消息历史，保留 Agent 实例 */
export function clearSqlAgentMessages() {
  return api.post('/agent/sql/messages/clear')
}

/** 完全销毁 Agent 实例 */
export function resetSqlAgent() {
  return api.delete('/agent/sql/reset')
}
