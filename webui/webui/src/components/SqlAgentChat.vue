<script setup>
import { ref, computed, nextTick, watch, onUnmounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { getToken, safeJsonParse } from '@/utils'
import { ChatDotSquare, Close, Promotion, ArrowDown, SwitchButton, CircleClose } from '@element-plus/icons-vue'
import { ElMessageBox, ElMessage } from 'element-plus'
import { getSqlAgentStatus, getSqlAgentMessages, clearSqlAgentMessages, resetSqlAgent } from '@/api/agent'
import defaultAvatar from '@/assets/user/vue-color-avatar.png'
import '@lottiefiles/lottie-player'
import { marked } from 'marked'

// 配置 marked
marked.setOptions({
  breaks: true,
  gfm: true,
})

function renderMarkdown(text) {
  if (!text) return ''
  return marked.parse(text)
}

const auth = useAuthStore()
const userAvatar = computed(() => auth.user?.avatar_url || defaultAvatar)

// ── State machine ──
// closed → checking → connecting → initializing → ready
//                     ↑              ↑
//              recovering (恢复中)   clearing (清理中)
const open = ref(false)
const phase = ref('closed')  // closed | checking | connecting | initializing | recovering | clearing | ready
const connected = ref(false)

const messages = ref([])
const inputText = ref('')
const currentStream = ref('')
const streaming = ref(false)
const chatBody = ref(null)
const mascotRef = ref(null)
const wrapperRef = ref(null)
const panelRef = ref(null)

const P_W = 520, P_H = 500, P_GAP = 130, M_S = 110

const phaseLabel = {
  checking:     '检测中...',
  connecting:   '连接中...',
  initializing: '初始化中...',
  recovering:   '恢复中...',
  clearing:     '清理中...',
  ready:        '在线',
}

// ── 面板 & 小人位置 ──
// dragPos 语义：
//   closed → 小人右下角偏移（拖小人，上下左右四边约束）
//   open   → 面板右下角偏移（拖面板，小人吸附右上角，仅约束上/左）

const panelStyle = computed(() => {
  if (!open.value) return {}
  const x = dragPos.value.x, y = dragPos.value.y
  return {
    right: Math.max(0, Math.min(x, innerWidth - P_W)) + 'px',
    bottom: Math.max(0, Math.min(y, innerHeight - P_H)) + 'px',
  }
})

const mascotStyle = computed(() => {
  const x = dragPos.value.x, y = dragPos.value.y
  if (open.value) {
    // 小人吸附面板右上角，始终 clamp 在视口内
    const px = Math.max(0, Math.min(x, innerWidth - P_W))
    const py = Math.max(0, Math.min(y, innerHeight - P_H))
    let mr = px + P_W - 30
    let mb = py + P_H - 30
    mr = Math.max(0, Math.min(mr, innerWidth - M_S))
    mb = Math.max(0, Math.min(mb, innerHeight - M_S))
    return { right: mr + 'px', bottom: mb + 'px' }
  }
  return {
    right: Math.max(0, Math.min(x, innerWidth - M_S)) + 'px',
    bottom: Math.max(0, Math.min(y, innerHeight - M_S)) + 'px',
  }
})

// ── 拖拽 ──

const dragPos = ref({ x: 24, y: 24 })
let dragging = false, hasMoved = false
let startX = 0, startY = 0, origX = 0, origY = 0
let dragSource = null  // 'mascot' | 'panel'

function onDragStart(e) {
  dragging = true; hasMoved = false
  dragSource = e.currentTarget === wrapperRef.value ? 'mascot' : 'panel'
  startX = e.touches ? e.touches[0].clientX : e.clientX
  startY = e.touches ? e.touches[0].clientY : e.clientY
  origX = dragPos.value.x; origY = dragPos.value.y
  document.addEventListener('mousemove', onDragMove)
  document.addEventListener('mouseup', onDragEnd)
  document.addEventListener('touchmove', onDragMove, { passive: false })
  document.addEventListener('touchend', onDragEnd)
}

function onDragMove(e) {
  if (!dragging) return
  e.preventDefault()
  const cx = e.touches ? e.touches[0].clientX : e.clientX
  const cy = e.touches ? e.touches[0].clientY : e.clientY
  const dx = startX - cx, dy = startY - cy
  if (Math.abs(dx) < 3 && Math.abs(dy) < 3) return
  if (!hasMoved) {
    hasMoved = true
    wrapperRef.value.style.transition = 'none'
    if (panelRef.value) panelRef.value.style.transition = 'none'
  }
  if (open.value) {
    // 展开：拖的是面板，x/y 均以面板完整可见为界
    const x = Math.max(0, Math.min(innerWidth - P_W, origX + dx))
    const y = Math.max(0, Math.min(innerHeight - P_H, origY + dy))
    dragPos.value = { x, y }
  } else {
    // 关闭：拖的是小人，四边全约束
    const x = Math.max(0, Math.min(innerWidth - M_S, origX + dx))
    const y = Math.max(0, Math.min(innerHeight - M_S, origY + dy))
    dragPos.value = { x, y }
  }
  wrapperRef.value.style.right = dragPos.value.x + 'px'
  wrapperRef.value.style.bottom = dragPos.value.y + 'px'
}

function onDragEnd() {
  dragging = false
  document.removeEventListener('mousemove', onDragMove)
  document.removeEventListener('mouseup', onDragEnd)
  document.removeEventListener('touchmove', onDragMove)
  document.removeEventListener('touchend', onDragEnd)
  wrapperRef.value.style.transition = ''
  if (panelRef.value) panelRef.value.style.transition = ''
  // 只有点小人才切换窗口，拖拽/点击面板内部不触发
  if (!hasMoved && dragSource === 'mascot') { toggleChat(); return }
}

// ── WebSocket ──

let socket = null
const clicking = ref(false)

// ── 断开下拉 ──

function handleDisconnect(command) {
  if (command === 'close-session') {
    // 仅断开 WS，Agent 保留，清空前端消息
    if (socket) {
      socket.close(1000)
      socket = null
    }
    streaming.value = false
    currentStream.value = ''
    messages.value = []
    phase.value = 'closed'
    connected.value = false
    open.value = false
  } else if (command === 'destroy-agent') {
    // 断开 WS + 销毁 Agent
    if (socket) {
      socket.close(1000)
      socket = null
    }
    streaming.value = false
    currentStream.value = ''
    resetSqlAgent().catch(() => {})
    messages.value = []
    phase.value = 'closed'
    connected.value = false
    open.value = false
    ElMessage.success('Agent 已关闭')
  }
}

// ── 主入口：点击小人 ──

const _mascotHome = { x: 24, y: 24 }  // 默认右下角位置

async function toggleChat() {
  clicking.value = true
  setTimeout(() => { clicking.value = false }, 400)

  const closing = open.value
  if (closing) {
    // 收回前先把小人归位，避免闪烁
    dragPos.value = { ..._mascotHome }
  }
  open.value = !open.value

  if (!closing && phase.value === 'closed') {
    await checkStatusAndConnect()
  }
}

async function checkStatusAndConnect() {
  phase.value = 'checking'

  try {
    const res = await getSqlAgentStatus()
    const status = res.status  // 'idle' | 'disconnected' | 'ready'

    if (status === 'disconnected') {
      // 没有历史消息 → 直接连接，不弹窗
      if (!res.message_count) {
        connect()
        return
      }
      // 有历史会话 → 弹窗询问
      try {
        await ElMessageBox.confirm(
          `检测到活跃会话（${res.message_count} 条历史消息），是否恢复？`,
          '恢复会话',
          {
            confirmButtonText: '恢复',
            cancelButtonText: '不恢复',
            type: 'info',
            showClose: false,
          }
        )
        // 用户选择"恢复"
        await recoverHistory()
      } catch {
        // 用户选择"不恢复"或关闭弹窗
        await clearAndConnect()
      }
    } else {
      // idle 或 ready → 直接连接
      connect()
    }
  } catch (e) {
    // 请求失败也直接连接（容错）
    connect()
  }
}

async function recoverHistory() {
  phase.value = 'recovering'
  try {
    const res = await getSqlAgentMessages()
    if (res.messages && res.messages.length > 0) {
      messages.value = res.messages
      await nextTick()
      scrollToBottom()
    }
  } catch {
    // 获取失败不影响连接
  }
  connect()
}

async function clearAndConnect() {
  phase.value = 'clearing'
  try {
    await clearSqlAgentMessages()
  } catch {
    // 清理失败也继续连接
  }
  messages.value = []
  connect()
}

// ── WebSocket 连接 ──

function connect() {
  const token = getToken()
  if (!token) return

  // recovering/clearing 阶段不覆盖，保持当前状态给用户看到
  if (phase.value !== 'recovering' && phase.value !== 'clearing') {
    phase.value = 'connecting'
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  const url = `${protocol}//${host}/api/agent/sql/chat?token=${token}`

  try {
    socket = new WebSocket(url)

    socket.onopen = () => {
      connected.value = true
    }

    socket.onclose = () => {
      connected.value = false
      streaming.value = false
      phase.value = 'closed'
      open.value = false
    }

    socket.onerror = () => {
      connected.value = false
      phase.value = 'closed'
    }

    socket.onmessage = (event) => {
      const raw = event.data
      if (!raw) return
      if (!raw.startsWith('{')) {
        if (streaming.value) currentStream.value += raw
        return
      }
      try {
        const msg = safeJsonParse(raw)

        if (msg.code && msg.code !== 200) {
          messages.value.push({ role: 'system', content: `${msg.message || '请求失败'}` })
          return
        }

        const statusMsg = msg.message
        if (statusMsg === '连接成功') {
          // recovering/clearing → 保持当前阶段，等待后续消息切换为 ready
          if (phase.value === 'recovering' || phase.value === 'clearing') {
            return
          }
          phase.value = 'initializing'
          return
        }
        if (statusMsg === '对话历史已恢复' || statusMsg === '初始化完成，可以开始查询') {
          phase.value = 'ready'
          return
        }
        if (statusMsg) {
          messages.value.push({ role: 'system', content: statusMsg })
          return
        }

        const evt = msg.data
        if (!evt) return

        if (evt.type === 'text') {
          streaming.value = true
          currentStream.value += evt.content || ''
        } else if (evt.type === 'tool') {
          streaming.value = true
          currentStream.value += `\n· 调用工具: ${evt.name}...\n`
        } else if (evt.type === 'end') {
          streaming.value = false
          if (currentStream.value) {
            messages.value.push({ role: 'assistant', content: currentStream.value })
            currentStream.value = ''
          }
        }
      } catch {
        if (event.data && streaming.value) {
          currentStream.value += event.data
        }
      }
    }
  } catch {
    phase.value = 'closed'
    connected.value = false
  }
}

function sendMessage() {
  const text = inputText.value.trim()
  if (!text || !socket || socket.readyState !== WebSocket.OPEN || phase.value !== 'ready') return

  messages.value.push({ role: 'user', content: text })
  inputText.value = ''
  streaming.value = true
  currentStream.value = ''
  socket.send(text)
}

function handleKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (chatBody.value) {
      chatBody.value.scrollTop = chatBody.value.scrollHeight
    }
  })
}

const isBusy = computed(() =>
  ['checking', 'connecting', 'initializing', 'recovering', 'clearing'].includes(phase.value)
)

watch(messages, scrollToBottom, { deep: true })
watch(currentStream, scrollToBottom)

onUnmounted(() => {
  if (socket) {
    socket.close(1000)
    socket = null
  }
})
</script>

<template>
  <template v-if="auth.isAdmin">
    <!-- 聊天面板 -->
    <transition name="chat-fade">
      <div
        v-if="open"
        ref="panelRef"
        class="chat-panel"
        :style="panelStyle"
      >
        <div class="chat-header" @mousedown="onDragStart" @touchstart="onDragStart">
          <div class="chat-header-left">
            <el-icon :size="18"><Promotion /></el-icon>
            <span class="chat-title">数据助手</span>
            <span class="chat-status" :class="{ online: phase === 'ready', busy: isBusy }">
              {{ phaseLabel[phase] || phase }}
            </span>
          </div>
          <!-- 关闭下拉框 -->
          <el-dropdown trigger="click" @command="handleDisconnect" popper-class="disconnect-popper">
            <span class="disconnect-trigger" @mousedown.stop>
              关闭<el-icon class="trigger-arrow"><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="close-session">
                  <el-icon><SwitchButton /></el-icon>会话
                </el-dropdown-item>
                <el-dropdown-item command="destroy-agent" divided class="dropdown-item--danger">
                  <el-icon><CircleClose /></el-icon>Agent
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>

        <div class="chat-body" ref="chatBody">
          <div v-if="!messages.length && !streaming" class="chat-empty">
            <el-icon :size="32"><ChatDotSquare /></el-icon>
            <p v-if="phase === 'checking'">正在检测会话状态...</p>
            <p v-else-if="phase === 'connecting'">正在连接服务器...</p>
            <p v-else-if="phase === 'initializing'">AI 助手正在初始化，请稍候...</p>
            <p v-else-if="phase === 'recovering'">正在恢复历史记录...</p>
            <p v-else-if="phase === 'clearing'">正在清理旧会话...</p>
            <p v-else-if="phase === 'ready'">输入自然语言查询数据库</p>
            <p v-else>点击连接开始</p>
          </div>

          <div
            v-for="(msg, idx) in messages"
            :key="idx"
            :class="['chat-msg', msg.role === 'user' ? 'msg-right' : 'msg-left']"
          >
            <template v-if="msg.role === 'user'">
              <el-avatar :size="28" :src="userAvatar" class="msg-avatar-img" />
            </template>
            <span v-else class="msg-avatar" :class="{ 'msg-avatar-sys': msg.role === 'system', 'msg-avatar-ai': msg.role !== 'system' }">
              <el-icon v-if="msg.role !== 'system'" :size="14"><Cpu /></el-icon>
              <span v-else class="sys-mark">!</span>
            </span>
            <div class="msg-body">
              <div class="msg-content" v-html="renderMarkdown(msg.content)"></div>
            </div>
          </div>

          <div v-if="streaming && currentStream" class="chat-msg msg-left">
            <span class="msg-avatar msg-avatar-ai">
              <el-icon :size="14"><Cpu /></el-icon>
            </span>
            <div class="msg-body msg-body-stream">
              <div class="msg-content" v-html="renderMarkdown(currentStream) + '<span class=\'typing\'>|</span>'"></div>
            </div>
          </div>
        </div>

        <div class="chat-input-area">
          <el-input
            v-model="inputText"
            :placeholder="phase === 'ready' ? '输入查询...' : '等待就绪...'"
            :disabled="phase !== 'ready'"
            @keydown="handleKeydown"
            size="small"
            class="chat-input-inner"
          >
            <template #suffix>
              <el-button
                text
                size="small"
                :disabled="phase !== 'ready' || !inputText.trim()"
                @click="sendMessage"
              >
                发送
              </el-button>
            </template>
          </el-input>
        </div>
      </div>
    </transition>

    <!-- 小人 -->
    <div
      ref="wrapperRef"
      class="sql-agent-wrapper"
      :style="mascotStyle"
      @mousedown="onDragStart"
      @touchstart="onDragStart"
    >
      <div
        class="fab"
        :class="{ thinking: streaming, clicking: clicking }"
        title="数据助手 — 拖拽移动，点击打开"
      >
        <lottie-player
          ref="mascotRef"
          src="/mascot-lottie.json"
          mode="normal"
          speed="0.8"
          style="width:110px;height:110px"
          loop
          autoplay
        />
      </div>
    </div>
  </template>
</template>

<!-- style unchanged, keep existing -->
<style scoped>
.sql-agent-wrapper {
  position: fixed;
  z-index: calc(var(--z-modal, 400) + 10);
  transition: right 0.4s cubic-bezier(0.34, 1.56, 0.64, 1),
              bottom 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.fab {
  width: 110px;
  height: 110px;
  background: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: grab;
  user-select: none;
  -webkit-user-select: none;
  transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.fab:active {
  cursor: grabbing;
}

.mascot-container {
  width: 110px;
  height: 110px;
  filter: drop-shadow(0 2px 8px rgba(0, 0, 0, 0.08));
  transition: filter 0.3s ease, transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.fab.clicking .mascot-container {
  animation: mascot-pop 0.35s ease;
}

@keyframes mascot-pop {
  0%   { transform: scale(1); }
  40%  { transform: scale(1.12); }
  100% { transform: scale(1); }
}

.mascot-container :deep(svg) {
  width: 110px !important;
  height: 110px !important;
}

.fab:hover .mascot-container {
  filter: drop-shadow(0 4px 14px rgba(0, 0, 0, 0.12));
}

.fab.thinking .mascot-container {
  filter: drop-shadow(0 4px 12px rgba(37, 99, 235, 0.15));
}

.chat-panel {
  position: fixed;
  z-index: var(--z-modal, 400);
  width: 520px;
  height: 500px;
  max-height: calc(100vh - 120px);
  background: #fff;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: 0 8px 40px rgba(0,0,0,0.15);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  background: var(--color-primary-dark);
  color: #fff;
  flex-shrink: 0;
  cursor: grab;
  user-select: none;
}

.chat-header:active {
  cursor: grabbing;
}

.chat-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.chat-title {
  font-weight: 600;
  font-size: 13px;
}

.chat-status {
  font-size: 11px;
  opacity: 0.9;
  padding: 1px 6px;
  border-radius: var(--radius-full);
  background: rgba(16, 185, 129, 0.5);
}

.chat-status.busy {
  background: rgba(245, 158, 11, 0.5);
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 0.9; }
  50% { opacity: 0.5; }
}

/* ── 断开下拉 ── */

.disconnect-trigger {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: rgba(255,255,255,0.82);
  cursor: pointer;
  padding: 4px 10px;
  border-radius: var(--radius-xs);
  transition: color 0.2s, background 0.2s;
  user-select: none;
}

.disconnect-trigger:hover {
  color: #fff;
  background: rgba(255,255,255,0.12);
}

.trigger-arrow {
  font-size: 11px;
  transition: transform 0.2s;
}

.disconnect-trigger:hover .trigger-arrow {
  transform: translateY(1px);
}


.chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 10px 12px;
  font-size: 12px;
  line-height: 1.55;
  background: var(--color-bg);
}

.chat-empty {
  text-align: center;
  padding: 40px 0;
  color: var(--color-text-muted);
}

.chat-empty p {
  margin-top: 4px;
  font-size: 12px;
}

.chat-msg {
  margin-bottom: 12px;
  display: flex;
  align-items: flex-end;
  gap: 6px;
}

.chat-msg.msg-right {
  flex-direction: row-reverse;
  align-items: flex-start;
}

.chat-msg.msg-left {
  flex-direction: row;
  align-items: flex-start;
}

.msg-avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  font-size: 11px;
  font-weight: 700;
  color: #fff;
  flex-shrink: 0;
}

.msg-avatar-ai {
  background: linear-gradient(135deg, #7c3aed 0%, #a855f7 100%);
  box-shadow: 0 1px 4px rgba(124, 58, 237, 0.3);
}

.msg-avatar-sys {
  background: var(--color-warning);
}

.sys-mark {
  line-height: 1;
}

.msg-left .msg-avatar-sys { background: var(--color-warning); }
.msg-right .msg-avatar { background: var(--color-primary); }

.msg-body {
  max-width: 78%;
  flex: 0 1 auto;
}

.msg-body-stream {
  flex: 1 1 auto;
  min-width: 0;
}

.chat-msg.msg-right .msg-body {
  text-align: right;
}

.msg-avatar-img {
  display: block;
  border: 2px solid var(--color-primary);
  flex-shrink: 0;
}

.msg-left .msg-avatar-img {
  border-color: #10b981;
}

.chat-msg.system .msg-avatar {
  background: var(--color-warning);
}

.msg-content {
  display: inline-block;
  max-width: 100%;
  overflow-x: auto;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 5px 10px;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  line-height: 1.6;
  text-align: left;
}

/* ── Markdown 表格 ── */
.msg-content :deep(table) {
  border-collapse: collapse;
  margin: 8px 0;
  font-size: 11px;
  width: 100%;
}

.msg-content :deep(th),
.msg-content :deep(td) {
  border: 1px solid var(--color-border);
  padding: 4px 8px;
  text-align: left;
  white-space: normal;
}

.msg-content :deep(th) {
  background: var(--color-primary-bg);
  font-weight: 600;
}

.msg-content :deep(tr:nth-child(even)) {
  background: rgba(0, 0, 0, 0.02);
}

.msg-content :deep(code) {
  background: rgba(0, 0, 0, 0.06);
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 11px;
}

.msg-content :deep(pre) {
  background: rgba(0, 0, 0, 0.04);
  padding: 8px;
  border-radius: 4px;
  overflow-x: auto;
  margin: 4px 0;
}

.msg-content :deep(pre code) {
  background: none;
  padding: 0;
}

.msg-right .msg-content {
  background: var(--color-primary-bg);
  border-color: var(--color-primary-border);
  border-bottom-right-radius: 2px;
}

.msg-left .msg-content {
  border-bottom-left-radius: 2px;
}

.typing {
  animation: blink 1s infinite;
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

.chat-input-area {
  padding: 8px 10px;
  border-top: 1px solid var(--color-border);
  flex-shrink: 0;
  background: var(--color-surface);
}

.chat-input-inner {
  font-size: 12px;
}

.chat-fade-enter-active {
  transition: opacity 0.25s ease, transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.chat-fade-leave-active { transition: opacity 0.15s ease; }
.chat-fade-enter-from {
  opacity: 0;
  transform: scale(0.8) translateY(20px);
}
.chat-fade-leave-to {
  opacity: 0;
  transform: scale(0.8);
}

@media (max-width: 480px) {
  .chat-panel {
    width: calc(100vw - 32px);
    right: -8px;
    height: 420px;
  }
}
</style>

<!-- 下拉面板样式（非 scoped，popper 渲染在 body 下）-->
<style>
.disconnect-popper {
  min-width: 120px !important;
  padding: 2px 0 !important;
}

.disconnect-popper .el-dropdown-menu__item {
  display: flex !important;
  align-items: center;
  gap: 8px;
  padding: 6px 14px !important;
  font-size: 13px;
}

.disconnect-popper .el-dropdown-menu__item .el-icon {
  font-size: 15px;
  flex-shrink: 0;
}

.disconnect-popper .dropdown-item--danger {
  color: #e74c3c !important;
}

.disconnect-popper .dropdown-item--danger:hover {
  background: #fef0f0 !important;
  color: #c0392b !important;
}
</style>
