<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { getInterviewReport } from '@/api/interview'
import { formatDate } from '@/utils'
import { TrendCharts } from '@element-plus/icons-vue'

const route = useRoute()

const report = ref(null)
const loading = ref(true)
const invalid = ref(false)
const errorMsg = ref('')

function getSessionId() {
  return route.params.sessionId
}

const isValidSessionId = computed(() => {
  const id = getSessionId()
  return id && id !== 'undefined' && id !== 'null' && /^\d+$/.test(id)
})

async function fetchReport() {
  const sessionId = getSessionId()
  if (!isValidSessionId.value) {
    invalid.value = true
    loading.value = false
    return
  }
  invalid.value = false
  errorMsg.value = ''
  loading.value = true
  try {
    report.value = await getInterviewReport(sessionId)
  } catch (err) {
    errorMsg.value = err?.message || '加载报告失败'
    report.value = null
  } finally {
    loading.value = false
  }
}

onMounted(fetchReport)
watch(() => route.params.sessionId, fetchReport)

// Flatten the nested backend response { session, records, evaluation }
const evalData = computed(() => report.value?.evaluation || {})
const sessionData = computed(() => report.value?.session || {})
const records = computed(() => report.value?.records || [])

function formatDuration(seconds) {
  if (!seconds && seconds !== 0) return '-'
  const s = Number(seconds)
  if (s < 60) return `${s} 秒`
  const mins = Math.floor(s / 60)
  const secs = s % 60
  return secs > 0 ? `${mins} 分 ${secs} 秒` : `${mins} 分钟`
}

function scoreColor(score) {
  if (score >= 80) return '#10b981'
  if (score >= 60) return '#f59e0b'
  return '#ef4444'
}

function passLabel(v) {
  if (v === 1 || v === true) return '面试通过 ✓'
  if (v === 0 || v === false) return '未通过'
  return '待评价'
}

function passType(v) {
  if (v === 1 || v === true) return 'success'
  if (v === 0 || v === false) return 'danger'
  return 'warning'
}
</script>

<template>
  <div class="report-page" v-loading="loading">
    <h1 class="page-title">
      <el-icon :size="28"><TrendCharts /></el-icon>
      面试报告
    </h1>

    <template v-if="report">
      <!-- Score overview -->
      <el-card class="section-card">
        <div class="score-overview">
          <div class="score-circle" :style="{ color: scoreColor(evalData.total_score) }">
            <span class="score-num">{{ evalData.total_score ?? '-' }}</span>
            <span class="score-label">总分</span>
          </div>
          <div class="score-result">
            <el-tag
              :type="passType(evalData.is_pass)"
              size="large"
              effect="dark"
            >
              {{ passLabel(evalData.is_pass) }}
            </el-tag>
            <p class="score-summary" v-if="evalData.summary">{{ evalData.summary }}</p>
          </div>
        </div>
      </el-card>

      <!-- Strengths -->
      <el-card class="section-card" v-if="evalData.strengths">
        <template #header>
          <h3>💪 优点</h3>
        </template>
        <div class="content-text">{{ evalData.strengths }}</div>
      </el-card>

      <!-- Weaknesses -->
      <el-card class="section-card" v-if="evalData.weaknesses">
        <template #header>
          <h3>🎯 待改进</h3>
        </template>
        <div class="content-text">{{ evalData.weaknesses }}</div>
      </el-card>

      <!-- Suggestion -->
      <el-card class="section-card" v-if="evalData.suggestion">
        <template #header>
          <h3>💡 建议</h3>
        </template>
        <div class="content-text">{{ evalData.suggestion }}</div>
      </el-card>

      <!-- Q&A Records -->
      <el-card class="section-card" v-if="records.length">
        <template #header>
          <h3>📝 答题记录</h3>
        </template>
        <div v-for="(rec, idx) in records" :key="rec.id || idx" class="record-item">
          <div class="record-header">
            <el-tag size="small" type="info">第 {{ rec.round_number }} 题</el-tag>
            <span class="record-score" :style="{ color: scoreColor(rec.score) }">
              {{ rec.score ?? '-' }} 分
            </span>
          </div>
          <p class="record-question"><strong>问题：</strong>{{ rec.question }}</p>
          <p class="record-answer"><strong>回答：</strong>{{ rec.answer }}</p>
          <p class="record-comment" v-if="rec.comment"><strong>点评：</strong>{{ rec.comment }}</p>
        </div>
      </el-card>

      <!-- Session info -->
      <el-card class="section-card">
        <template #header>
          <h3>面试记录</h3>
        </template>
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="会话ID">{{ sessionData.id || sessionId }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ sessionData.status }}</el-descriptions-item>
          <el-descriptions-item label="开始时间" v-if="sessionData.start_time">{{ formatDate(sessionData.start_time) }}</el-descriptions-item>
          <el-descriptions-item label="结束时间" v-if="sessionData.end_time">{{ formatDate(sessionData.end_time) }}</el-descriptions-item>
          <el-descriptions-item label="时长" v-if="sessionData.duration">{{ formatDuration(sessionData.duration) }}</el-descriptions-item>
        </el-descriptions>
      </el-card>
    </template>

    <el-empty v-else-if="!loading && !invalid && !errorMsg" description="暂无面试报告" />

    <el-empty v-else-if="invalid" description="无效的面试会话ID">
      <el-button type="primary" @click="$router.push('/interview/sessions')">返回面试记录</el-button>
    </el-empty>

    <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" style="margin-top: 16px" />
  </div>
</template>

<style scoped>
.report-page {
  max-width: 1100px;
}

.page-title {
  font-size: var(--font-size-2xl);
  margin-bottom: var(--space-6);
  color: var(--color-text);
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.section-card {
  margin-bottom: var(--space-4);
}

.section-card h3 {
  margin: 0;
}

.score-overview {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  padding: var(--space-5);
}

.score-circle {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 130px;
  min-width: 130px;
  height: 130px;
  border-radius: 50%;
  border: 6px solid currentColor;
  background: var(--color-surface);
  overflow: hidden;
  flex-shrink: 0;
}

.score-num {
  font-size: 36px;
  font-weight: 800;
}

.score-label {
  font-size: 14px;
  opacity: 0.7;
}

.score-summary {
  color: var(--color-text-secondary);
  margin: var(--space-3) 0 0;
  line-height: 1.6;
}

.content-text {
  white-space: pre-wrap;
  line-height: 1.8;
  color: var(--color-text-secondary);
}

/* Q&A Records */
.record-item {
  padding: var(--space-4);
  background: var(--color-bg-alt);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-3);
}

.record-item:last-child {
  margin-bottom: 0;
}

.record-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-3);
}

.record-score {
  font-weight: 700;
  font-size: var(--font-size-base);
}

.record-question,
.record-answer,
.record-comment {
  margin: var(--space-2) 0;
  font-size: var(--font-size-sm);
  line-height: 1.6;
  color: var(--color-text-secondary);
}

.record-answer {
  color: var(--color-text);
}
</style>
