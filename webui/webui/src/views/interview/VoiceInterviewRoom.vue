<script setup>
import { ref, watch, nextTick, onBeforeUnmount, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useVoiceWebSocket } from '@/composables/useVoiceWebSocket'
import { ElMessage } from 'element-plus'
import VoiceVisual from './VoiceVisual.vue'

const route = useRoute()
const router = useRouter()
const jobId = route.params.jobId

const {
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
  onAudioDone,
} = useVoiceWebSocket(jobId)

// ── 状态标签 ────────────────────────────────────────────
const statusLabel = computed(() => {
  const map = {
    idle: '',
    connecting: '正在连接 AI 面试官...',
    initializing: '正在初始化面试...',
    ready: '准备就绪',
    calling: 'AI 思考中...',
    speaking: '面试官提问中',
    listening: '正在聆听您的回答...',
    reporting: '正在生成面试报告...',
    done: '面试已完成',
  }
  return map[status.value] || ''
})

const statusBg = computed(() => {
  const map = {
    idle: 'linear-gradient(135deg, #F5F6FA 0%, #EEF0F6 100%)',
    connecting: 'linear-gradient(135deg, #EFF3FF 0%, #E0E8FF 100%)',
    initializing: 'linear-gradient(135deg, #EFF3FF 0%, #E0E8FF 100%)',
    ready: 'linear-gradient(135deg, #F0F4FF 0%, #E8EEFF 100%)',
    calling: 'linear-gradient(135deg, #FEF3C7 0%, #FDE68A 50%, #FEF3C7 100%)',
    speaking: 'linear-gradient(135deg, #EEF2FF 0%, #E2E9FF 50%, #F0F4FF 100%)',
    listening: 'linear-gradient(135deg, #EDF1FF 0%, #F0F5FF 50%, #EEE8FF 100%)',
    reporting: 'linear-gradient(135deg, #F5F3FF 0%, #EDE9FE 100%)',
    done: 'linear-gradient(135deg, #ECFDF5 0%, #D1FAE5 100%)',
  }
  return map[status.value] || map.idle
})

// ── 音频采集 ────────────────────────────────────────────
let mediaRecorder = null
let audioContext = null
let analyser = null
let silenceTimer = null
let audioSeq = 0
let _recordingStopped = false  // stopRecording 之后丢弃残留 chunk
let _noiseCalibrated = false    // 环境噪声是否已校准
let silenceThreshold = 15       // 动态校准，启动时根据环境噪声自动调整
const SILENCE_TIMEOUT = 2500    // 静音超时（毫秒），中文回答停顿较长

async function startRecording() {
  try {
    console.log('[CKPT-REC-1] 请求麦克风权限（降噪+回声消除）...')
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        noiseSuppression: true,       // 浏览器降噪
        echoCancellation: true,       // 回声消除（防止录到 TTS 播放声）
        autoGainControl: true,        // 自动增益
        channelCount: 1,              // 单声道
      },
    })
    console.log('[CKPT-REC-2] 麦克风已获取, tracks=', stream.getAudioTracks().length)
    audioContext = new AudioContext()
    const source = audioContext.createMediaStreamSource(stream)
    analyser = audioContext.createAnalyser()
    analyser.fftSize = 256
    source.connect(analyser)

    // 优先 webm/opus，降级到浏览器默认
    let mimeType = 'audio/webm;codecs=opus'
    if (!MediaRecorder.isTypeSupported(mimeType)) {
      mimeType = 'audio/webm'
      console.log('[CKPT-REC-3] opus 不支持，降级为', mimeType)
    }
    console.log('[CKPT-REC-3] MediaRecorder MIME=', mimeType)
    mediaRecorder = new MediaRecorder(stream, { mimeType })
    audioSeq = 0
    _recordingStopped = false

    mediaRecorder.ondataavailable = async (e) => {
      if (_recordingStopped || e.data.size === 0) return
      console.log('[CKPT-REC-4] ondataavailable size=', e.data.size, 'seq=', audioSeq + 1)
      const base64 = await blobToBase64(e.data)
      audioSeq++
      sendAudioChunk(base64, audioSeq)
    }

    mediaRecorder.onerror = (e) => {
      console.error('[CKPT-REC-ERR] MediaRecorder 错误', e)
    }

    // 首次录音时校准环境噪声阈值（后续轮次复用）
    if (!_noiseCalibrated) {
      await calibrateNoiseFloor()
      _noiseCalibrated = true
    }

    mediaRecorder.start(500)
    console.log('[CKPT-REC-5] MediaRecorder 已启动, state=', mediaRecorder.state)
    checkSilence()
  } catch (err) {
    console.error('[CKPT-REC-ERR] 麦克风访问失败', err)
    ElMessage.error('无法访问麦克风，请检查浏览器权限设置')
  }
}

function stopRecording() {
  console.log('[CKPT-REC-6] stopRecording 调用, mediaRecorder.state=', mediaRecorder?.state)
  _recordingStopped = true  // 屏蔽 stop() 触发的残留 chunk
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop()
  }
  if (audioContext && audioContext.state !== 'closed') {
    audioContext.close()
  }
  clearTimeout(silenceTimer)
  silenceTimer = null
  mediaRecorder = null
  audioContext = null
  analyser = null
}

async function calibrateNoiseFloor(durationMs = 1500) {
  if (!analyser) return
  const samples = []
  const start = Date.now()
  const binCount = analyser.frequencyBinCount
  console.log('[CKPT-CAL] 开始环境噪声校准, 采集 %sms...', durationMs)
  while (Date.now() - start < durationMs) {
    const data = new Uint8Array(binCount)
    analyser.getByteFrequencyData(data)
    const avg = data.reduce((a, b) => a + b, 0) / binCount
    samples.push(avg)
    await new Promise(r => requestAnimationFrame(r))
  }
  const noiseFloor = samples.reduce((a, b) => a + b, 0) / samples.length
  silenceThreshold = Math.max(noiseFloor * 2, 8)
  console.log('[CKPT-CAL] 校准完成: noiseFloor=%.1f, threshold=%d', noiseFloor, silenceThreshold)
}

function checkSilence() {
  if (!analyser) return
  const dataArray = new Uint8Array(analyser.frequencyBinCount)
  analyser.getByteFrequencyData(dataArray)
  const avg = dataArray.reduce((a, b) => a + b, 0) / dataArray.length

  if (avg < silenceThreshold) {
    if (!silenceTimer) {
      console.log('[CKPT-REC-7] 检测到静音，启动 %sms 定时器', SILENCE_TIMEOUT)
      silenceTimer = setTimeout(() => {
        console.log('[CKPT-REC-8] 静音超时，自动触发 endSpeaking')
        endSpeaking()
        clearTimeout(silenceTimer)
        silenceTimer = null
      }, SILENCE_TIMEOUT)
    }
  } else {
    clearTimeout(silenceTimer)
    silenceTimer = null
  }

  if (mediaRecorder && mediaRecorder.state === 'recording') {
    requestAnimationFrame(checkSilence)
  }
}

function blobToBase64(blob) {
  return new Promise((resolve) => {
    const reader = new FileReader()
    reader.onloadend = () => {
      const result = reader.result
      const base64 = result.split(',')[1] || result
      resolve(base64)
    }
    reader.readAsDataURL(blob)
  })
}

// ── 操作 ────────────────────────────────────────────────
function handleStart()           { connect() }
function handleConfirm()         { confirmStart() }
function handleEndSpeaking()     { endSpeaking() }
function handleEndInterview()    { endInterview() }
function handleViewReport()      { disconnect(); if (sessionId.value) router.push(`/interview/report/${sessionId.value}`) }
function handleExit()            { disconnect(); router.back() }

// ── 音频播完 → 自动开始录音 ──────────────────────────
onAudioDone.value = () => {
  // 仅在面试官说完话后自动开始录音（speaking → listening）
  if (status.value === 'speaking' && !mediaRecorder) {
    console.log('[CKPT-AUTO] 音频播完，自动开始录音')
    status.value = 'listening'
    startRecording()
  }
}

// ── 状态监听 ────────────────────────────────────────────
watch(status, (newVal, oldVal) => {
  // 手动触发时停止录音（用户点"说完"、结束面试等）
  if (oldVal === 'listening' && newVal !== 'listening' && mediaRecorder) {
    stopRecording()
  }
  if (newVal === 'done') {
    stopRecording()
    sessionId.value = route.query.session_id || sessionId.value
  }
})

watch(error, (val) => {
  if (val) ElMessage.error(val)
})

onBeforeUnmount(() => {
  stopRecording()
  disconnect()
})
</script>

<template>
  <div class="voice-interview" :style="{ background: statusBg }">
    <Transition name="voice-fade" mode="out-in">
      <!-- ── Connecting / Initializing / Reporting ──────── -->
      <div v-if="status === 'connecting' || status === 'initializing' || status === 'reporting'" key="loading" class="voice-card">
        <VoiceVisual :status="status" />
        <p class="voice-status">{{ statusLabel }}</p>
        <span class="voice-dot-pulse"></span>
      </div>

      <!-- ── Ready ─────────────────────────────────────── -->
      <div v-else-if="status === 'ready'" key="ready" class="voice-card voice-card--glass">
        <VoiceVisual status="ready" />
        <p class="voice-welcome">{{ welcomeText }}</p>
        <div class="voice-actions">
          <el-button type="primary" size="large" round @click="handleConfirm">
            开始面试
          </el-button>
        </div>
      </div>

      <!-- ── Calling / Speaking / Listening ─────────────── -->
      <div
        v-else-if="status === 'calling' || status === 'speaking' || status === 'listening'"
        key="active"
        class="voice-card voice-card--glass voice-card--active"
      >
        <VoiceVisual :status="status" :analyser="analyser" />

        <div class="call-info">
          <p class="voice-status">{{ statusLabel }}</p>
          <!-- 圆点进度指示器 -->
          <div v-if="totalQuestions" class="voice-dots">
            <span
              v-for="i in totalQuestions"
              :key="i"
              class="voice-dot"
              :class="{
                'voice-dot--done': i < answeredCount,
                'voice-dot--current': i === answeredCount && status === 'listening',
              }"
            ></span>
          </div>
        </div>

        <div class="call-actions">
          <el-button
            v-if="status === 'listening'"
            type="primary"
            size="large"
            round
            @click="handleEndSpeaking"
          >
            说完
          </el-button>
          <el-button
            v-if="status !== 'speaking' && status !== 'calling'"
            type="danger"
            size="large"
            round
            plain
            @click="handleEndInterview"
          >
            结束通话
          </el-button>
        </div>
      </div>

      <!-- ── Done ──────────────────────────────────────── -->
      <div v-else-if="status === 'done'" key="done" class="voice-card voice-card--glass">
        <div class="voice-done-check">
          <svg viewBox="0 0 52 52" class="voice-checkmark">
            <circle class="voice-checkmark__circle" cx="26" cy="26" r="25" fill="none" />
            <path class="voice-checkmark__check" fill="none" d="M14 27l7 7 16-16" />
          </svg>
        </div>
        <p class="voice-status">{{ statusLabel }}</p>
        <p v-if="summaryText" class="voice-summary">{{ summaryText }}</p>
        <div class="voice-actions">
          <el-button type="primary" size="large" round @click="handleViewReport">
            查看面试报告
          </el-button>
        </div>
      </div>

      <!-- ── Idle / Error ──────────────────────────────── -->
      <div v-else key="idle" class="voice-card">
        <div class="voice-idle-icon">
          <svg viewBox="0 0 64 64" width="64" height="64" fill="none">
            <rect x="18" y="10" width="28" height="44" rx="14" stroke="currentColor" stroke-width="2.5" />
            <line x1="28" y1="18" x2="28" y2="28" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
            <line x1="36" y1="18" x2="36" y2="28" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
            <circle cx="32" cy="38" r="3" fill="currentColor" />
          </svg>
        </div>
        <p class="voice-status" v-if="error">{{ error }}</p>
        <p class="voice-hint" v-else>点击下方按钮，开始 AI 语音面试</p>
        <div class="voice-actions">
          <el-button type="primary" size="large" round @click="handleStart" v-if="status === 'idle'">
            连接面试官
          </el-button>
          <el-button size="large" round @click="handleExit">返回</el-button>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
/* ── 容器 & 背景 ──────────────────────────────────────── */
.voice-interview {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: calc(100vh - 120px);
  transition: background 0.8s ease;
  overflow: hidden;
}

/* ── 过渡动画 ──────────────────────────────────────────── */
.voice-fade-enter-active {
  transition: opacity 0.35s ease, transform 0.35s ease;
}
.voice-fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.voice-fade-enter-from {
  opacity: 0;
  transform: translateY(12px);
}
.voice-fade-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

/* ── 卡片 ─────────────────────────────────────────────── */
.voice-card {
  text-align: center;
  max-width: 440px;
  width: 100%;
  padding: var(--space-10) var(--space-8);
  border-radius: var(--radius-2xl);
}

.voice-card--glass {
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.6);
  box-shadow: var(--shadow-lg);
}

.voice-card--active {
  padding: var(--space-8) var(--space-8) var(--space-6);
}

/* ── 状态文字 ──────────────────────────────────────────── */
.voice-status {
  font-size: var(--font-size-lg);
  font-weight: 500;
  color: var(--color-text);
  margin: var(--space-4) 0 var(--space-2);
}

.voice-hint {
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
  margin: var(--space-3) 0 var(--space-6);
}

.voice-welcome {
  font-size: var(--font-size-base);
  color: var(--color-text-secondary);
  margin: var(--space-4) 0 var(--space-6);
  line-height: 1.6;
  white-space: pre-wrap;
}

.voice-summary {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  margin: var(--space-3) 0 var(--space-5);
  line-height: 1.6;
  white-space: pre-wrap;
  max-height: 160px;
  overflow-y: auto;
}

/* ── 加载点点 ─────────────────────────────────────────── */
.voice-dot-pulse {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-primary);
  margin-top: var(--space-2);
  animation: dot-blink 1.2s ease-in-out infinite;
}

@keyframes dot-blink {
  0%, 100% { opacity: 0.2; transform: scale(0.8); }
  50%      { opacity: 1;   transform: scale(1.2); }
}

/* ── 圆点进度 ─────────────────────────────────────────── */
.voice-dots {
  display: flex;
  gap: 8px;
  justify-content: center;
  margin-top: var(--space-2);
}

.voice-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--color-border-strong);
  transition: all 0.35s ease;
}

.voice-dot--done {
  background: var(--color-primary);
  transform: scale(0.85);
}

.voice-dot--current {
  background: var(--color-primary);
  transform: scale(1.25);
  box-shadow: 0 0 8px rgba(37, 99, 235, 0.4);
  animation: dot-current 1.2s ease-in-out infinite;
}

@keyframes dot-current {
  0%, 100% { box-shadow: 0 0 4px rgba(37, 99, 235, 0.3); }
  50%      { box-shadow: 0 0 14px rgba(37, 99, 235, 0.55); }
}

/* ── 通话操作区 ──────────────────────────────────────── */
.call-info {
  text-align: center;
}

.call-actions {
  display: flex;
  justify-content: center;
  gap: var(--space-4);
  margin-top: var(--space-6);
}

/* ── 通用按钮行（idle / ready / done 等单/双按钮） ──── */
.voice-actions {
  display: flex;
  justify-content: center;
  gap: var(--space-3);
  margin-top: var(--space-5);
}

/* ── Idle 图标 ───────────────────────────────────────── */
.voice-idle-icon {
  color: var(--color-text-muted);
  margin-bottom: var(--space-2);
  opacity: 0.5;
}

/* ── Done checkmark 动画 ─────────────────────────────── */
.voice-done-check {
  width: 64px;
  height: 64px;
  margin: 0 auto var(--space-4);
}

.voice-checkmark {
  width: 64px;
  height: 64px;
}

.voice-checkmark__circle {
  stroke: var(--color-success);
  stroke-width: 2.5;
  stroke-dasharray: 166;
  stroke-dashoffset: 166;
  animation: circle-draw 0.6s ease-out forwards;
}

.voice-checkmark__check {
  stroke: var(--color-success);
  stroke-width: 3;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-dasharray: 48;
  stroke-dashoffset: 48;
  animation: check-draw 0.4s 0.4s ease-out forwards;
}

@keyframes circle-draw {
  to { stroke-dashoffset: 0; }
}

@keyframes check-draw {
  to { stroke-dashoffset: 0; }
}

/* ── 暗色模式 ──────────────────────────────────────────── */
@media (prefers-color-scheme: dark) {
  .voice-card--glass {
    background: rgba(30, 33, 48, 0.78);
    border-color: rgba(255, 255, 255, 0.08);
  }

  .voice-checkmark__circle {
    stroke: var(--color-success);
  }

  .voice-checkmark__check {
    stroke: var(--color-success);
  }
}
</style>
