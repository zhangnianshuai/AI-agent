import { ref, onUnmounted } from 'vue'
import { createInterviewSocket } from '@/api/interview'
import { getToken, safeJsonParse } from '@/utils'

export function useWebSocket(jobId) {
  const socket = ref(null)
  const messages = ref([])
  const isConnected = ref(false)
  const isStreaming = ref(false)
  const thinking = ref(false)
  const currentStream = ref('')
  const evaluation = ref(null)
  const sessionId = ref(null)
  const finished = ref(false)
  const error = ref('')
  const totalQuestions = ref(0)       // 总题数，从欢迎消息解析
  const answeredCount = ref(0)        // 已答题目数
  const generatingReport = ref(false) // 是否正在生成报告

  // ── TTS 语音播报（Web Speech API）──
  const ttsEnabled = ref(false)
  let speechBuffer = ''
  let speaking = false

  let _voices = []
  if ('speechSynthesis' in window) {
    _voices = speechSynthesis.getVoices() || []
    speechSynthesis.onvoiceschanged = () => {
      _voices = speechSynthesis.getVoices() || []
    }
  }

  function _getBestVoice() {
    const preferred = ['Xiaoxiao', 'Yunxi', 'Xiaoyi', 'Hanhan', 'Tingting', 'Meijia']
    for (const name of preferred) {
      const v = _voices.find(v => v.lang.startsWith('zh') && v.name.includes(name))
      if (v) return v
    }
    return _voices.find(v => v.lang.startsWith('zh')) || null
  }

  function _stripMarkdown(text) {
    return text
      .replace(/\*\*(.+?)\*\*/g, '$1')
      .replace(/__(.+?)__/g, '$1')
      .replace(/\*(.+?)\*/g, '$1')
      .replace(/_(.+?)_/g, '$1')
      .replace(/`{1,3}[^`]*`{1,3}/g, '')
      .replace(/^#{1,6}\s+/gm, '')
      .replace(/^[-*+]\s+/gm, '')
      .replace(/^\d+\.\s+/gm, '')
      .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
      .replace(/!\[([^\]]*)\]\([^)]+\)/g, '$1')
      .replace(/^---+/gm, '')
      .replace(/^>\s?/gm, '')
  }

  function speakSentence(text) {
    if (!('speechSynthesis' in window)) return
    const clean = _stripMarkdown(text).trim()
    if (!clean) { speaking = false; flushSpeech(); return }

    const u = new SpeechSynthesisUtterance(clean)
    u.lang = 'zh-CN'
    u.rate = 2.0
    u.pitch = 1.0
    const voice = _getBestVoice()
    if (voice) u.voice = voice
    u.onstart = () => { speaking = true }
    u.onend = () => { speaking = false; flushSpeech() }
    u.onerror = () => { speaking = false; flushSpeech() }
    speechSynthesis.speak(u)
  }

  function flushSpeech() {
    if (speaking || !speechBuffer) return
    const m = speechBuffer.match(/^([^。！？\n]+[。！？\n]+)/)
    if (m) {
      speechBuffer = speechBuffer.slice(m[1].length)
      speakSentence(m[1])
    }
  }

  function feedSpeech(text) {
    if (!ttsEnabled.value) return
    speechBuffer += text
    if (!speaking) flushSpeech()
  }

  function cancelSpeech() {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel()
    }
    speechBuffer = ''
    speaking = false
  }

  // ── WebSocket ────────────────────────────────────────────

  let reconnectTimer = null
  let reconnectCount = 0
  const MAX_RECONNECT = 3

  function connect() {
    const token = getToken()
    if (!token) { error.value = '未登录，无法开始面试'; return }

    try {
      socket.value = createInterviewSocket(jobId, token)

      socket.value.onopen = () => {
        isConnected.value = true
        error.value = ''
        reconnectCount = 0
      }

      socket.value.onmessage = (event) => {
        if (event.data instanceof ArrayBuffer) {
          const blob = new Blob([event.data], { type: 'audio/mp3' })
          const url = URL.createObjectURL(blob)
          const a = new Audio()
          a.src = url
          a.onended = () => URL.revokeObjectURL(url)
          a.play().catch(() => {})
          return
        }

        const raw = event.data
        if (!raw) return

        if (!raw.startsWith('{')) {
          if (isStreaming.value) {
            currentStream.value += raw
            feedSpeech(raw)
          }
          return
        }

        try {
          const msg = safeJsonParse(raw)
          const type = msg.data?.type

          if (type === 'stream_start') {
            thinking.value = false
            isStreaming.value = true
            currentStream.value = ''
            return
          }

          if (type === 'stream_end') {
            isStreaming.value = false
            if (speechBuffer && !speaking) {
              speakSentence(speechBuffer)
              speechBuffer = ''
            }
            if (currentStream.value) {
              messages.value.push({
                role: 'ai',
                content: currentStream.value,
                time: new Date().toISOString(),
              })
              currentStream.value = ''
            }
            return
          }

          if (type === 'ping') return

          if (msg.data?.session_id) {
            sessionId.value = msg.data.session_id
            generatingReport.value = false
            finished.value = true
            thinking.value = false
          }

          if (msg.message) {
            // 从欢迎消息中解析总题数
            if (totalQuestions.value <= 0) {
              const m = msg.message.match(/共\s*(\d+)\s*题/)
              if (m) totalQuestions.value = parseInt(m[1], 10)
            }
            // 检测报告生成阶段，关掉 thinking 防止两个气泡重叠
            if (/生成.*报告|稍候/.test(msg.message)) {
              thinking.value = false
              generatingReport.value = true
            }
            const isSysNotify = !msg.data?.type
            messages.value.push({
              role: isSysNotify ? 'notify' : 'system',
              content: msg.message,
              time: new Date().toISOString(),
            })
          }

          if (msg.code && msg.code !== 200) {
            error.value = msg.message || '服务器错误'
            isConnected.value = false
            finished.value = true
          }
        } catch {
          if (event.data && isStreaming.value) {
            currentStream.value += event.data
          }
        }
      }

      socket.value.onclose = (event) => {
        isConnected.value = false
        isStreaming.value = false
        finished.value = true
        const NO_RECONNECT_CODES = [1000, 4000, 4001]
        if (NO_RECONNECT_CODES.includes(event.code)) return
        if (reconnectCount >= MAX_RECONNECT) {
          error.value = '面试连接失败，请检查后端服务是否启动，稍后重试'
          return
        }
        reconnectCount++
        const delay = Math.min(1000 * Math.pow(2, reconnectCount), 10000)
        reconnectTimer = setTimeout(() => connect(), delay)
      }

      socket.value.onerror = () => {
        error.value = 'WebSocket 连接失败，请检查后端是否启动'
        isConnected.value = false
      }
    } catch (err) {
      error.value = '连接失败: ' + err.message
    }
  }

  function sendMessage(content) {
    if (!socket.value || socket.value.readyState !== WebSocket.OPEN) {
      error.value = '连接已断开'
      return
    }
    messages.value.push({ role: 'user', content, time: new Date().toISOString() })
    // 排除开场确认和"结束面试"，其余用户消息视为答题
    const skipKw = ['结束面试', '退出', 'quit', '开始', 'ready', '是', '可以', '好']
    if (!skipKw.some(kw => content.trim().startsWith(kw))) {
      answeredCount.value++
    }
    thinking.value = true
    currentStream.value = ''
    socket.value.send(content)
  }

  function disconnect() {
    clearTimeout(reconnectTimer)
    if (socket.value) { socket.value.close(1000); socket.value = null }
    isConnected.value = false
    isStreaming.value = false
    thinking.value = false
    cancelSpeech()
  }

  onUnmounted(() => {
    disconnect()
  })

  return {
    messages, isConnected, isStreaming, thinking, ttsEnabled,
    currentStream, evaluation, sessionId, finished, error,
    totalQuestions, answeredCount, generatingReport,
    connect, sendMessage, disconnect,
  }
}
