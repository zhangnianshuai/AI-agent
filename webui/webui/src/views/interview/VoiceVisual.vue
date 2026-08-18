<script setup>
/**
 * 语音面试可视化组件
 * - calling: Lottie 动画 + 呼吸光晕（AI 说话中）
 * - listening: Lottie 动画 + 实时音量波形（用户说话中）
 * - 其他状态: 静态 Lottie
 */
import { ref, watch, onBeforeUnmount, nextTick } from 'vue'
import { DotLottie } from '@lottiefiles/dotlottie-web'

const props = defineProps({
  status: { type: String, default: 'idle' },
  analyser: { type: Object, default: null }, // AnalyserNode for waveform
})

const lottieCanvas = ref(null)
const waveCanvas = ref(null)
let dotLottie = null
let waveRaf = null

// ── Lottie ──────────────────────────────────────────────
function initLottie() {
  if (!lottieCanvas.value) return
  if (dotLottie) return
  dotLottie = new DotLottie({
    autoplay: true,
    loop: true,
    canvas: lottieCanvas.value,
    src: '/Phone call.lottie',
  })
}

function destroyLottie() {
  dotLottie?.destroy()
  dotLottie = null
}

// ── 波形绘制 ────────────────────────────────────────────
function startWaveform() {
  if (!props.analyser || !waveCanvas.value) return
  const canvas = waveCanvas.value
  const ctx = canvas.getContext('2d')
  const buffer = new Uint8Array(props.analyser.frequencyBinCount)
  const barCount = 5
  const barWidth = 4
  const gap = 6
  const totalWidth = barCount * barWidth + (barCount - 1) * gap
  const startX = (canvas.width - totalWidth) / 2

  function draw() {
    if (!props.analyser) return
    props.analyser.getByteFrequencyData(buffer)
    // 取低频段平均能量
    const slice = Math.floor(buffer.length / 3)
    const avg = buffer.slice(0, slice).reduce((a, b) => a + b, 0) / slice

    ctx.clearRect(0, 0, canvas.width, canvas.height)

    for (let i = 0; i < barCount; i++) {
      // 每根条随机抖动 + 能量驱动高度
      const energy = Math.min(avg / 256, 1)
      const baseHeight = 8
      const maxHeight = 36
      const jitter = Math.sin(Date.now() / 150 + i * 1.2) * 4
      const h = baseHeight + energy * (maxHeight - baseHeight) + jitter

      const x = startX + i * (barWidth + gap)
      const y = (canvas.height - h) / 2

      ctx.fillStyle = '#60A5FA'
      ctx.fillRect(x, y, barWidth, h)
    }

    waveRaf = requestAnimationFrame(draw)
  }

  draw()
}

function stopWaveform() {
  if (waveRaf) {
    cancelAnimationFrame(waveRaf)
    waveRaf = null
  }
  // 清空画布
  const canvas = waveCanvas.value
  if (canvas) {
    canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height)
  }
}

// ── 状态驱动 ────────────────────────────────────────────
watch(() => props.status, async (val) => {
  await nextTick()
  if (val === 'calling' || val === 'speaking' || val === 'listening' || val === 'ready' || val === 'connecting' || val === 'reporting') {
    initLottie()
  }

  if (val === 'listening') {
    startWaveform()
  } else {
    stopWaveform()
  }
}, { immediate: true })

onBeforeUnmount(() => {
  destroyLottie()
  stopWaveform()
})
</script>

<template>
  <div class="voice-visual" :class="`voice-visual--${status}`">
    <!-- Lottie 动画 -->
    <canvas ref="lottieCanvas" width="200" height="200" class="voice-visual__lottie"></canvas>

    <!-- calling / speaking: 呼吸光晕 -->
    <div v-if="status === 'calling' || status === 'speaking'" class="voice-visual__pulse"></div>

    <!-- listening: 音量波形 -->
    <canvas
      v-if="status === 'listening'"
      ref="waveCanvas"
      width="160"
      height="48"
      class="voice-visual__wave"
    ></canvas>
  </div>
</template>

<style scoped>
.voice-visual {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 200px;
  height: 200px;
  margin: 0 auto;
}

.voice-visual__lottie {
  width: 200px;
  height: 200px;
  position: relative;
  z-index: 2;
}

/* ── 呼吸光晕 ──────────────────────────────────────── */
.voice-visual__pulse {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 140px;
  height: 140px;
  margin: -70px 0 0 -70px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(37, 99, 235, 0.15) 0%, transparent 70%);
  animation: voice-pulse 1.8s ease-in-out infinite;
  z-index: 1;
}

@keyframes voice-pulse {
  0%, 100% { transform: scale(1); opacity: 0.4; }
  50%      { transform: scale(1.35); opacity: 1; }
}

/* ── 波形 ──────────────────────────────────────────── */
.voice-visual__wave {
  margin-top: 4px;
  z-index: 2;
  opacity: 0.9;
}
</style>
