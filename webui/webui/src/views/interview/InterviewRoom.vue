<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useWebSocket } from '@/composables/useWebSocket'
import { ElMessage } from 'element-plus'
import { Promotion, Close, Connection, Microphone, Cpu, PhoneFilled } from '@element-plus/icons-vue'
import defaultAvatar from '@/assets/user/vue-color-avatar.png'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const jobId = route.params.jobId
const userAvatar = computed(() => auth.user?.avatar_url || defaultAvatar)

const {
  messages,
  isConnected,
  isStreaming,
  thinking,
  ttsEnabled,
  currentStream,
  sessionId,
  finished,
  error: wsError,
  totalQuestions,
  answeredCount,
  connect,
  sendMessage,
  disconnect,
} = useWebSocket(jobId)

const inputText = ref('')
const chatContainer = ref(null)
const started = ref(false)

// ── 进度条 ──
const progressPercent = computed(() =>
  totalQuestions.value > 0
    ? Math.min(100, Math.round((answeredCount.value / totalQuestions.value) * 100))
    : 0
)

// 每回答一题进度+1（跳过开场"准备好了吗"的应答）
watch(messages, (newMsgs) => {
  const userMsgs = newMsgs.filter(m => m.role === 'user')
  answeredCount.value = Math.max(0, userMsgs.length - 1)
}, { deep: true })

function scrollToBottom() {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}

watch(messages, scrollToBottom, { deep: true })
watch(currentStream, scrollToBottom)

function handleStart() {
  connect()
  started.value = true
}

function handleSend() {
  const text = inputText.value.trim()
  // AI 未输出完成或正在思考时不允许发送
  if (!text || !isConnected.value || isStreaming.value || thinking.value) return

  sendMessage(text)
  inputText.value = ''
}

function handleKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

function handleEnd() {
  sendMessage('结束面试')
}

// ── 语音转文字 ──
const listening = ref(false)
let recognition = null

function toggleSpeechInput() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
  if (!SpeechRecognition) {
    ElMessage.warning('当前浏览器不支持语音识别，请使用 Chrome 或 Edge')
    return
  }

  if (listening.value) {
    recognition?.stop()
    return
  }

  recognition = new SpeechRecognition()
  recognition.lang = 'zh-CN'
  recognition.interimResults = true
  recognition.continuous = true

  recognition.onstart = () => { listening.value = true }
  recognition.onend = () => { listening.value = false }
  recognition.onerror = () => { listening.value = false }

  recognition.onresult = (e) => {
    let transcript = ''
    for (let i = e.resultIndex; i < e.results.length; i++) {
      transcript += e.results[i][0].transcript
    }
    inputText.value = transcript
  }

  recognition.start()
}

function handleExit() {
  disconnect()
  if (sessionId.value) {
    router.push(`/interview/report/${sessionId.value}`)
  } else {
    router.push('/')
  }
}

function renderMarkdown(text) {
  if (!text) return ''
  return text
    // Bold
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    // Italic
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // Heading ## → h4
    .replace(/^## (.+)$/gm, '<h4>$1</h4>')
    // Heading ### → h5
    .replace(/^### (.+)$/gm, '<h5>$1</h5>')
    // Horizontal rule
    .replace(/^---$/gm, '<hr>')
    // Unordered list items (lines starting with -)
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    // Ordered list items (lines starting with 1. 2. etc)
    .replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
    // Wrap consecutive <li> in <ul>
    .replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>')
    // Line breaks (but not inside tags)
    .replace(/\n\n/g, '<br><br>')
    .replace(/\n/g, '<br>')
}

onMounted(() => {
  // Can auto-start or wait for user action
})
</script>

<template>
  <div class="interview-room">
    <!-- Pre-start screen: 面试方式选择 -->
    <div v-if="!started" class="pre-start">
      <h2 class="pre-start-title">选择面试方式</h2>
      <p class="pre-start-subtitle">文字面试适合深度思考，语音面试更贴近真实场景</p>

      <div class="mode-cards">
        <!-- 文字面试 -->
        <div class="mode-card" :class="{ 'mode-card--active': interviewMode === 'text' }" @click="interviewMode = 'text'">
          <div class="mode-card__icon mode-card__icon--text">
            <el-icon :size="36"><Promotion /></el-icon>
          </div>
          <h3>文字面试</h3>
          <p class="mode-card__desc">通过文字与 AI 面试官交流，适合深度思考和反复推敲</p>
          <ul class="mode-card__features">
            <li><span class="feature-dot"></span> 15-30 分钟模拟面试</li>
            <li><span class="feature-dot"></span> AI 实时评分反馈</li>
            <li><span class="feature-dot"></span> 支持语音输入辅助</li>
            <li><span class="feature-dot"></span> 详细评价报告</li>
          </ul>
          <el-button type="primary" size="large" round class="mode-card__btn" @click.stop="handleStart">
            开始文字面试
          </el-button>
        </div>

        <!-- 语音面试 -->
        <div class="mode-card" :class="{ 'mode-card--active': interviewMode === 'voice' }" @click="interviewMode = 'voice'">
          <div class="mode-card__icon mode-card__icon--voice">
            <el-icon :size="36"><PhoneFilled /></el-icon>
          </div>
          <h3>语音面试</h3>
          <p class="mode-card__desc">与 AI 面试官实时语音通话，模拟真实面试的临场感</p>
          <ul class="mode-card__features">
            <li><span class="feature-dot"></span> 全程语音对话交互</li>
            <li><span class="feature-dot"></span> AI 实时评分反馈</li>
            <li><span class="feature-dot"></span> 无需打字，解放双手</li>
            <li><span class="feature-dot"></span> 详细评价报告</li>
          </ul>
          <el-button type="primary" size="large" round class="mode-card__btn" @click.stop="router.push(`/interview/voice/${jobId}`)">
            开始语音面试
          </el-button>
        </div>
      </div>
    </div>

    <!-- Interview chat -->
    <div v-else class="chat-area">
      <el-card class="chat-card">
        <template #header>
          <div class="chat-header">
            <span>
              <el-icon :color="isConnected ? '#67c23a' : '#f56c6c'">
                <Connection />
              </el-icon>
              {{ isConnected ? '面试进行中' : '未连接' }}
            </span>
            <div>
              <el-button
                size="small"
                :icon="Microphone"
                :type="ttsEnabled ? 'success' : 'info'"
                plain
                @click="ttsEnabled = !ttsEnabled"
                title="语音播报"
              >
                {{ ttsEnabled ? '语音开' : '语音关' }}
              </el-button>
              <el-button type="danger" plain size="small" @click="handleEnd" :disabled="finished">
                结束面试
              </el-button>
              <el-button size="small" :icon="Close" @click="handleExit">退出</el-button>
            </div>
          </div>
          <!-- 进度条 -->
          <div class="progress-bar-wrap">
            <div class="progress-track">
              <div class="progress-fill" :style="{ width: progressPercent + '%' }"></div>
            </div>
            <span class="progress-label">{{ answeredCount }} / {{ totalQuestions }} 题</span>
          </div>
        </template>

        <!-- Messages -->
        <div class="chat-messages" ref="chatContainer">
          <div v-if="!isConnected && !messages.length" class="connecting">
            <p>正在连接面试官...</p>
          </div>

          <div
            v-for="(msg, idx) in messages"
            :key="idx"
            :class="['message', msg.role === 'user' ? 'message-user' : msg.role === 'notify' ? 'message-notify' : 'message-ai']"
          >
            <template v-if="msg.role === 'user'">
              <el-avatar :size="28" :src="userAvatar" class="msg-avatar-img" />
            </template>
            <span v-else-if="msg.role === 'ai'" class="message-avatar message-avatar-ai">
              <el-icon :size="18"><Cpu /></el-icon>
            </span>
            <!-- 系统通知：无框无头像，纯文字居中 -->
            <div v-if="msg.role === 'notify'" class="notify-text">
              <div class="message-content" v-html="renderMarkdown(msg.content)"></div>
            </div>
            <!-- 普通消息：带气泡框 -->
            <div v-else class="message-body">
              <div class="message-time" v-if="msg.time">
                {{ new Date(msg.time).toLocaleTimeString() }}
              </div>
              <div class="message-bubble">
                <div class="message-content" v-html="renderMarkdown(msg.content)"></div>
              </div>
            </div>
          </div>

          <!-- AI thinking indicator -->
          <div v-if="thinking && !isStreaming" class="message message-ai">
            <span class="message-avatar message-avatar-ai">
              <el-icon :size="18"><Cpu /></el-icon>
            </span>
            <div class="message-body">
              <div class="message-bubble thinking-bubble">
                <span class="dot-pulse"></span>
              </div>
            </div>
          </div>

          <!-- Streaming message -->
          <div v-if="isStreaming" class="message message-ai">
            <span class="message-avatar message-avatar-ai">
              <el-icon :size="18"><Cpu /></el-icon>
            </span>
            <div class="message-body message-body-stream">
              <div class="message-bubble">
                <div class="message-content">{{ currentStream }}<span class="cursor">|</span></div>
              </div>
            </div>
          </div>
        </div>

        <!-- Input -->
        <div class="chat-input" v-if="!finished">
          <div class="input-row">
            <el-button
              :type="listening ? 'danger' : 'default'"
              :icon="Microphone"
              circle
              size="large"
              :class="{ recording: listening }"
              :disabled="!isConnected || isStreaming || thinking"
              @click="toggleSpeechInput"
              title="语音输入"
            />
            <el-input
              v-model="inputText"
              placeholder="输入你的回答..."
              :disabled="!isConnected || isStreaming || thinking"
              @keydown="handleKeydown"
              size="large"
              class="input-main"
            >
              <template #append>
                <el-button
                  type="primary"
                  :disabled="!isConnected || isStreaming || thinking || !inputText.trim()"
                  @click="handleSend"
                >
                  发送
                </el-button>
              </template>
            </el-input>
          </div>
        </div>

        <div class="chat-input" v-else>
          <el-alert
            title="面试已结束"
            type="success"
            show-icon
            :closable="false"
          >
            <template #default>
              <el-button type="primary" @click="sessionId && sessionId !== 'undefined' && router.push(`/interview/report/${sessionId}`)">
                查看详细报告
              </el-button>
            </template>
          </el-alert>
        </div>

        <el-alert v-if="wsError" :title="wsError" type="error" show-icon :closable="false" style="margin-top: 12px" />
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.interview-room {
  max-width: 960px;
  margin: 0 auto;
}

/* ── Pre-start screen ── */
.pre-start {
  padding: var(--space-6) var(--space-4);
}

.pre-start-title {
  text-align: center;
  font-size: var(--font-size-2xl);
  font-weight: 700;
  color: var(--color-text);
  margin-bottom: var(--space-2);
}

.pre-start-subtitle {
  text-align: center;
  font-size: var(--font-size-sm);
  color: var(--color-text-muted);
  margin-bottom: var(--space-8);
}

/* ── 面试方式卡片 ── */
.mode-cards {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-6);
}

.mode-card {
  background: var(--color-surface);
  border: 2px solid var(--color-border);
  border-radius: var(--radius-2xl);
  padding: var(--space-8) var(--space-6) var(--space-6);
  text-align: center;
  cursor: pointer;
  transition: all 0.25s ease;
  display: flex;
  flex-direction: column;
  align-items: center;
  outline: none;
}

.mode-card:focus-visible {
  outline: none;
}

.mode-card:hover {
  border-color: var(--color-primary);
  box-shadow: 0 4px 24px rgba(37, 99, 235, 0.1);
  transform: translateY(-2px);
}

.mode-card--active,
.mode-card--active:focus,
.mode-card--active:focus-visible {
  border-color: var(--color-border) !important;
  box-shadow: none !important;
  outline: none !important;
  background: var(--color-surface) !important;
}

.mode-card--active .el-button:focus,
.mode-card--active .el-button:focus-visible {
  outline: none !important;
  box-shadow: none !important;
}

.mode-card h3 {
  margin: var(--space-4) 0 var(--space-2);
  font-size: var(--font-size-lg);
  font-weight: 600;
  color: var(--color-text);
}

.mode-card__icon {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.mode-card__icon--text {
  background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
  color: #3b82f6;
}

.mode-card__icon--voice {
  background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
  color: #22c55e;
}

.mode-card__desc {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-4);
  line-height: 1.5;
}

.mode-card__features {
  list-style: none;
  padding: 0;
  margin: 0 0 var(--space-6);
  text-align: left;
  width: 100%;
}

.mode-card__features li {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) 0;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.feature-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-primary);
  flex-shrink: 0;
  opacity: 0.5;
}

.mode-card__btn {
  margin-top: auto;
  min-width: 180px;
}

.mode-card .el-button:focus-visible,
.mode-card .el-button:focus {
  outline: none !important;
  box-shadow: none !important;
}

/* ── Responsive ── */
@media (max-width: 640px) {
  .mode-cards {
    grid-template-columns: 1fr;
  }
}

/* ── Chat area ── */
.chat-card {
  height: calc(100vh - 120px);
  display: flex;
  flex-direction: column;
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.chat-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 0;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* ── Progress bar ── */
.progress-bar-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 10px;
}

.progress-track {
  flex: 1;
  height: 6px;
  background: var(--color-border);
  border-radius: 3px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--color-primary), #67c23a);
  border-radius: 3px;
  transition: width 0.5s ease;
}

.progress-label {
  font-size: 12px;
  color: var(--color-text-secondary);
  white-space: nowrap;
  font-weight: 600;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-4);
  background: var(--color-bg-alt);
}

.connecting {
  text-align: center;
  padding: 60px;
  color: var(--color-text-muted);
}

/* ── Message bubbles ── */
.message {
  display: flex;
  gap: 8px;
  margin-bottom: var(--space-4);
}

.message-ai {
  flex-direction: row;
  align-items: flex-start;       /* AI 头像始终在气泡左上角 */
}

.message-user {
  flex-direction: row-reverse;
  align-items: flex-start;
}

.message-user {
  align-items: flex-end;
}

.message-notify {
  justify-content: center;
  margin: var(--space-5) 0;
}

.message-body-notify {
  max-width: 85%;
  text-align: center;
}

.notify-text {
  width: 100%;
  text-align: center;
  color: var(--color-text-secondary);
  font-size: 13px;
  padding: var(--space-2) 0;
}

.notify-text :deep(.message-content) {
  text-align: center;
}

.message-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  color: #fff;
  flex-shrink: 0;
  background: var(--color-primary);
}

.message-avatar-ai {
  background: linear-gradient(135deg, #7c3aed 0%, #a855f7 100%);
  box-shadow: 0 1px 4px rgba(124, 58, 237, 0.3);
}

.msg-avatar-img {
  border: 2px solid var(--color-primary);
  flex-shrink: 0;
}

.message-body {
  max-width: 70%;
  flex: 0 1 auto;
}

.message-body-stream {
  flex: 1 1 auto;
  min-width: 0;
}

.message-time {
  font-size: 11px;
  color: var(--color-text-muted);
  margin-bottom: var(--space-1);
  padding: 0 4px;
}

.message-bubble {
  width: 100%;
  background: var(--color-surface);
  border-radius: var(--radius-lg);
  padding: var(--space-3) var(--space-4);
  box-shadow: none;
  border: 1px solid var(--color-border);
}

.message-ai .message-bubble {
  border-bottom-left-radius: var(--radius-xs);
}

.message-user .message-bubble {
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-bottom-right-radius: var(--radius-xs);
}

.message-content {
  word-break: break-word;
  line-height: 1.6;
  text-align: left;
  font-size: var(--font-size-sm);
}

.message-content :deep(h4) {
  margin: var(--space-3) 0 var(--space-2);
  font-size: 15px;
  font-weight: 600;
}

.message-content :deep(h5) {
  margin: var(--space-2) 0 var(--space-1);
  font-size: 14px;
  font-weight: 600;
}

.message-content :deep(strong) {
  font-weight: 600;
  color: inherit;
}

.message-content :deep(ul) {
  margin: var(--space-1) 0;
  padding-left: 18px;
}

.message-content :deep(li) {
  margin: 2px 0;
}

.message-content :deep(hr) {
  border: none;
  border-top: 1px solid var(--color-border);
  margin: var(--space-3) 0;
}

/* Typing cursor */
.cursor {
  animation: blink 1s infinite;
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

/* Generating report hint */
.generating-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--color-text-secondary);
}

/* AI thinking dots */
.thinking-bubble {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 60px;
  min-height: 36px;
}

.dot-pulse {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-primary);
  animation: dotPulse 1.2s infinite ease-in-out;
  position: relative;
}

.dot-pulse::before,
.dot-pulse::after {
  content: '';
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-primary);
  position: absolute;
  top: 0;
}

.dot-pulse::before {
  left: -16px;
  animation: dotPulse 1.2s infinite ease-in-out;
  animation-delay: 0.2s;
}

.dot-pulse::after {
  left: 16px;
  animation: dotPulse 1.2s infinite ease-in-out;
  animation-delay: 0.4s;
}

@keyframes dotPulse {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

/* ── Chat input ── */
.chat-input {
  padding: var(--space-3) var(--space-4);
  border-top: 1px solid var(--color-border);
  background: var(--color-surface);
}

.input-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.input-main {
  flex: 1;
}

.recording {
  animation: pulse-red 1.5s infinite;
  box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.5);
}

@keyframes pulse-red {
  0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.5); }
  70% { box-shadow: 0 0 0 8px rgba(239, 68, 68, 0); }
  100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
}

/* ── Responsive ── */
@media (max-width: 768px) {
  .message-body {
    max-width: 80%;
  }

  .mode-card {
    padding: var(--space-6) var(--space-4) var(--space-5);
  }
}
</style>
