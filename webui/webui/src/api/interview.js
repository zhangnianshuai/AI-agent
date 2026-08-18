import api from './index'

export function getInterviewReport(sessionId) {
  return api.get(`/interview/report/${sessionId}`)
}

export function listInterviewSessions() {
  return api.get('/interview/sessions')
}

export function deleteInterviewSession(sessionId) {
  return api.delete(`/interview/sessions/${sessionId}`)
}

// ── 候选人管理 ──
export function listCompanyCandidates(companyId, params = {}) {
  return api.get(`/interview/company/${companyId}/candidates`, { params })
}

export function setCandidatePass(sessionId, isPass) {
  return api.put(`/interview/candidates/${sessionId}/pass`, null, {
    params: { is_pass: isPass },
  })
}

/**
 * Create a WebSocket connection for the interview.
 * The token is sent as a query parameter for WebSocket auth.
 */
export function createInterviewSocket(jobId, token) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  const url = `${protocol}//${host}/api/interview/${jobId}?token=${token}`
  const ws = new WebSocket(url)
  ws.binaryType = 'arraybuffer'  // 接收 TTS 语音二进制帧
  return ws
}

/**
 * 语音面试 WebSocket 连接
 */
export function createVoiceInterviewSocket(jobId, token) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  const url = `${protocol}//${host}/api/interview/voice/${jobId}?token=${token}`
  return new WebSocket(url)
}
