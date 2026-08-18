/**
 * 语音面试 WebSocket Composable
 *
 * 与 useWebSocket.js（文字面试）对应的语音版本。
 * 管理 WebSocket 连接、音频播放队列、状态机。
 */

import { ref, onUnmounted } from 'vue'
import { createVoiceInterviewSocket } from '@/api/interview'
import { getToken } from '@/utils'

export function useVoiceWebSocket(jobId) {
  // ── 状态机 ────────────────────────────────────────────
  // idle → connecting → ready → calling ↔ listening → reporting → done
  const status = ref('idle')
  const welcomeText = ref('')
  const summaryText = ref('')
  const totalQuestions = ref(0)
  const answeredCount = ref(0)
  const sessionId = ref(null)
  const error = ref('')

  const socket = ref(null)
  const onTtsSentence = ref(null)  // 外部回调: (chunk) => {}
  const onStatusChange = ref(null) // 外部回调: (newStatus) => {}

  // ── 连接 ──────────────────────────────────────────────
  function connect() {
    const token = getToken()
    if (!token) {
      error.value = '未登录'
      return
    }

    status.value = 'connecting'
    console.log('[CKPT-FE-1] 开始连接 WebSocket, jobId=', jobId)

    try {
      const ws = createVoiceInterviewSocket(jobId, token)
      socket.value = ws

      ws.onopen = () => {
        console.log('[CKPT-FE-2] WebSocket 已连接')
      }

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)
          console.log('[CKPT-FE-3] 收到消息 type=', msg.type, 'state=', msg.state,
            msg.type === 'tts_sentence' ? 'audio_len=' + (msg.data?.length || 0) : '')
          handleMessage(msg)
        } catch {
          console.log('[CKPT-FE-3] 收到非JSON消息:', event.data?.substring(0, 50))
        }
      }

      ws.onclose = (e) => {
        console.log('[CKPT-FE-4] WebSocket 关闭 code=', e.code, '当前状态=', status.value)
        // 非正常结束的连接关闭，强制回到 idle 以触发清理
        if (status.value !== 'done') {
          const wasActive = status.value === 'listening' || status.value === 'calling' || status.value === 'speaking'
          status.value = 'idle'
          if (wasActive) {
            error.value = e.code !== 1000 ? '连接已断开' : '面试已结束'
          }
        }
      }

      ws.onerror = (e) => {
        console.error('[CKPT-FE-5] WebSocket 错误', e)
        error.value = 'WebSocket 连接失败'
        status.value = 'idle'
      }
    } catch (err) {
      console.error('[CKPT-FE-6] 连接异常', err)
      error.value = '连接失败: ' + err.message
      status.value = 'idle'
    }
  }

  // ── 消息处理 ──────────────────────────────────────────
  function handleMessage(msg) {
    switch (msg.type) {
      case 'status': {
        const prev = status.value
        status.value = msg.state
        if (msg.welcome) welcomeText.value = msg.welcome
        if (msg.summary) summaryText.value = msg.summary
        if (msg.total) totalQuestions.value = msg.total
        if (msg.session_id) sessionId.value = msg.session_id
        // speaking 现在随第一个 tts_sentence 一起到达，此处仅做兜底
        if (msg.state === 'speaking' && prev !== 'speaking') {
          answeredCount.value++
          _serverWantsListen = false
        }
        if (onStatusChange.value) onStatusChange.value(msg.state, prev)
        break
      }

      case 'tts_sentence': {
        // 第一个语音块附带 speaking 状态 → 即时切换 UI
        if (msg.state === 'speaking' && status.value !== 'speaking') {
          status.value = 'speaking'
          _serverWantsListen = false
        }
        enqueueAudio(msg)
        break
      }

      case 'listening': {
        // 服务端通知可以开始听，但需等所有音频播完
        console.log('[CKPT-FE-STATE] 收到 listening, pending=%s', _audioPending)
        _serverWantsListen = true
        // listening 到达 = 当前问题已问完，更新进度
        if (status.value !== 'listening') answeredCount.value++
        if (_audioPending === 0) {
          _tryFireAudioDone()  // 无待播音频，直接触发
        }
        break
      }

      case 'listening_timeout': {
        status.value = 'calling'
        error.value = '回答超时'
        break
      }

      case 'error': {
        error.value = msg.message || '服务器错误'
        status.value = 'idle'
        break
      }

      default:
        break
    }
  }

  // ── 音频播放（Promise 链 + seq 校验）─────────────────
  let _playChain = Promise.resolve()
  let _audioPending = 0
  let _expectedSeq = 0       // 期望的下一个播放 seq
  let _serverWantsListen = false  // 服务端已发 listening，等音频播完
  const onAudioDone = ref(null)   // 外部回调: 可以开始录音时触发

  function enqueueAudio(chunk) {
    const seq = chunk.seq || 0
    const len = chunk.data?.length || 0

    // seq 连续性校验
    if (_expectedSeq > 0 && seq !== _expectedSeq) {
      console.warn('[CKPT-FE-AUDIO-0] seq 跳跃! 期望=%s 实际=%s', _expectedSeq, seq)
    }
    _expectedSeq = seq + 1

    console.log('[CKPT-FE-AUDIO-1] 入队 seq=', seq, 'audio_len=', len, 'pending=', _audioPending + 1)

    _audioPending++
    _playChain = _playChain.then(() => {
      return playAudioChunk(chunk).finally(() => {
        _audioPending--
        console.log('[CKPT-FE-AUDIO-7] 播放完成 seq=%s 剩余pending=%s wantListen=%s',
                    seq, _audioPending, _serverWantsListen)
        _tryFireAudioDone()
      })
    })
  }

  function _tryFireAudioDone() {
    // 两个条件同时满足才触发：服务端发了 listening + 所有音频播完
    if (_audioPending === 0 && _serverWantsListen && onAudioDone.value) {
      console.log('[CKPT-FE-AUDIO-8] 条件满足 → onAudioDone')
      _serverWantsListen = false
      _expectedSeq = 0
      onAudioDone.value()
    }
  }

  function playAudioChunk(chunk) {
    return new Promise((resolve) => {
      const dataUrl = `data:audio/mpeg;base64,${chunk.data}`
      const audio = new Audio(dataUrl)

      // 预加载：确保浏览器缓冲完毕再播
      audio.preload = 'auto'

      const cleanup = () => {
        audio.oncanplaythrough = null
        audio.onended = null
        audio.onerror = null
        resolve()
      }

      audio.oncanplaythrough = () => {
        console.log('[CKPT-FE-AUDIO-2] 缓冲完成, 开始播放 seq=', chunk.seq)
        audio.play().catch((err) => {
          console.error('[CKPT-FE-AUDIO-3] play 失败 seq=', chunk.seq, err)
          cleanup()
        })
      }

      audio.onended = () => {
        console.log('[CKPT-FE-AUDIO-4] 播放完成 seq=', chunk.seq)
        cleanup()
      }

      audio.onerror = (e) => {
        console.error('[CKPT-FE-AUDIO-5] 加载失败 seq=', chunk.seq, e)
        cleanup()
      }

      // 超时保护：5 秒后无论如何继续
      setTimeout(() => {
        if (audio.ended || audio.error) return
        console.warn('[CKPT-FE-AUDIO-6] 播放超时, 强制继续 seq=', chunk.seq)
        audio.pause()
        cleanup()
      }, 5000)
    })
  }

  // ── 发送方法 ──────────────────────────────────────────
  function confirmStart() {
    console.log('[CKPT-FE-SEND-1] 发送 voice_start')
    send({ type: 'voice_start' })
  }

  function sendAudioChunk(base64Data, seq) {
    console.log('[CKPT-FE-SEND-2] 发送 voice_data seq=', seq, 'len=', base64Data?.length)
    send({ type: 'voice_data', seq, data: base64Data })
  }

  function endSpeaking() {
    console.log('[CKPT-FE-SEND-3] 发送 voice_end')
    send({ type: 'voice_end' })
  }

  function endInterview() {
    console.log('[CKPT-FE-SEND-4] 发送 end_interview')
    send({ type: 'end_interview' })
  }

  function send(data) {
    if (socket.value && socket.value.readyState === WebSocket.OPEN) {
      socket.value.send(JSON.stringify(data))
    } else {
      console.warn('[CKPT-FE-SEND-5] WebSocket 未连接, readyState=', socket.value?.readyState, '丢弃消息 type=', data.type)
    }
  }

  function disconnect() {
    if (socket.value) {
      socket.value.close(1000)
      socket.value = null
    }
    // 重置播放链
    _playChain = Promise.resolve()
    _audioPending = 0
    _expectedSeq = 0
    _serverWantsListen = false
  }

  onUnmounted(() => {
    disconnect()
  })

  return {
    status,
    welcomeText,
    summaryText,
    totalQuestions,
    answeredCount,
    sessionId,
    error,
    connect,
    confirmStart,
    sendAudioChunk,
    endSpeaking,
    endInterview,
    disconnect,
    onTtsSentence,
    onStatusChange,
    onAudioDone,
  }
}
