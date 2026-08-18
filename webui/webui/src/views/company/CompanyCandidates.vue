<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { listCompanyCandidates, setCandidatePass, getInterviewReport } from '@/api/interview'
import { formatDate } from '@/utils'
import { ElMessage } from 'element-plus'
import { View, Refresh } from '@element-plus/icons-vue'

const route = useRoute()
const companyId = route.params.id

const candidates = ref([])
const total = ref(0)
const loading = ref(true)
const page = ref(1)
const pageSize = ref(10)

const filters = reactive({
  is_pass: null,
  job_title: '',
  job_location: '',
})

const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref(null)
const updatingPass = ref(false)

function scoreColor(score) {
  if (!score && score !== 0) return '#94a3b8'
  if (score >= 80) return '#10b981'
  if (score >= 60) return '#f59e0b'
  return '#ef4444'
}

async function fetchCandidates() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (filters.is_pass !== null && filters.is_pass !== '') params.is_pass = filters.is_pass
    if (filters.job_title) params.job_title = filters.job_title
    if (filters.job_location) params.job_location = filters.job_location
    const data = await listCompanyCandidates(companyId, params)
    candidates.value = data.items || []
    total.value = data.total || 0
  } catch { candidates.value = [] }
  finally { loading.value = false }
}

function onFilterChange() {
  page.value = 1
  fetchCandidates()
}

function passLabel(v) {
  if (v === 1 || v === true) return '通过'
  if (v === 0 || v === false) return '未通过'
  return '待评价'
}

function passType(v) {
  if (v === 1 || v === true) return 'success'
  if (v === 0 || v === false) return 'danger'
  return 'info'
}

function detailPassLabel(v) {
  if (v === 1 || v === true) return '通过 ✓'
  if (v === 0 || v === false) return '未通过'
  return '待评价'
}

function detailPassType(v) {
  if (v === 1 || v === true) return 'success'
  if (v === 0 || v === false) return 'danger'
  return 'warning'
}

async function viewDetail(row) {
  detailVisible.value = true
  detailLoading.value = true
  detail.value = null
  try {
    detail.value = await getInterviewReport(row.session_id)
    // 同步当前行的 is_pass 到 detail，确保弹窗内是最新的
    if (detail.value?.evaluation) {
      detail.value.evaluation._row = row
    }
  } catch {
    detail.value = null
  } finally {
    detailLoading.value = false
  }
}

async function onPassChange(newPass) {
  const row = detail.value?.evaluation?._row
  if (!row) return
  const oldPass = row.is_pass
  const label = newPass === 1 ? '通过' : newPass === 0 ? '未通过' : '待评价'
  updatingPass.value = true
  try {
    await setCandidatePass(row.session_id, newPass)
    row.is_pass = newPass
    if (detail.value?.evaluation) {
      detail.value.evaluation.is_pass = newPass
    }
    ElMessage.success(`已标记为${label}`)
  } catch {
    // 失败回滚
    row.is_pass = oldPass
  }
  finally { updatingPass.value = false }
}

watch(() => route.params.id, (id) => { if (id) fetchCandidates() })
onMounted(fetchCandidates)
</script>

<template>
  <div class="candidate-page">
    <div class="page-header">
      <h2 class="page-title">候选人管理</h2>
    </div>

    <!-- Filters -->
    <el-card class="filter-card">
      <el-form :model="filters" inline>
        <el-form-item label="通过状态">
          <el-select v-model="filters.is_pass" placeholder="全部" clearable style="width:120px" @change="onFilterChange">
            <el-option :value="1" label="通过" />
            <el-option :value="0" label="未通过" />
          </el-select>
        </el-form-item>
        <el-form-item label="岗位名称">
          <el-input v-model="filters.job_title" placeholder="搜索岗位" clearable style="width:180px" @clear="onFilterChange" @keyup.enter="onFilterChange" />
        </el-form-item>
        <el-form-item label="工作地址">
          <el-input v-model="filters.job_location" placeholder="输入地址" clearable style="width:140px" @clear="onFilterChange" @keyup.enter="onFilterChange" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Refresh" @click="onFilterChange">查询</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- Table -->
    <el-card>
      <el-table :data="candidates" v-loading="loading" stripe>
        <el-table-column prop="real_name" label="姓名" width="100" />
        <el-table-column prop="email" label="邮箱" min-width="180" show-overflow-tooltip />
        <el-table-column prop="phone" label="手机号" width="130" />
        <el-table-column prop="job_title" label="面试岗位" min-width="140" show-overflow-tooltip />
        <el-table-column prop="job_location" label="工作地址" width="110" />
        <el-table-column label="通过状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="passType(row.is_pass)" size="small">
              {{ passLabel(row.is_pass) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right" align="center">
          <template #default="{ row }">
            <el-button type="primary" link :icon="View" @click="viewDetail(row)">面试详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loading && candidates.length === 0" description="暂无候选人面试记录" />

      <div class="pagination-wrap" v-if="total > pageSize">
        <el-pagination v-model:current-page="page" :page-size="pageSize" :total="total"
          background layout="prev, pager, next" @current-change="fetchCandidates" />
      </div>
    </el-card>

    <!-- Detail Dialog -->
    <el-dialog v-model="detailVisible" width="800px" top="5vh">
      <template #header>
        <div class="dialog-header">
          <span class="dialog-title">面试详情</span>
          <el-select
            v-if="detail"
            v-model="detail.evaluation._row.is_pass"
            size="small"
            class="pass-select"
            :loading="updatingPass"
            @change="onPassChange"
          >
            <el-option :value="1" label="通过" />
            <el-option :value="0" label="未通过" />
            <el-option :value="null" label="待评价" />
          </el-select>
        </div>
      </template>
      <div v-loading="detailLoading">
        <template v-if="detail">
          <div class="score-overview" v-if="detail.evaluation">
            <div class="score-circle" :style="{ color: scoreColor(detail.evaluation.total_score) }">
              <span class="score-num">{{ detail.evaluation.total_score ?? '-' }}</span>
              <span class="score-label">总分</span>
            </div>
            <div class="score-result">
              <el-tag :type="detailPassType(detail.evaluation.is_pass)" size="large" effect="dark">
                {{ detailPassLabel(detail.evaluation.is_pass) }}
              </el-tag>
              <p class="score-summary" v-if="detail.evaluation.summary">{{ detail.evaluation.summary }}</p>
            </div>
          </div>

          <el-card class="d-section" v-if="detail.evaluation?.strengths">
            <template #header><h3>💪 优点</h3></template>
            <div class="content-text">{{ detail.evaluation.strengths }}</div>
          </el-card>
          <el-card class="d-section" v-if="detail.evaluation?.weaknesses">
            <template #header><h3>🎯 待改进</h3></template>
            <div class="content-text">{{ detail.evaluation.weaknesses }}</div>
          </el-card>

          <el-card class="d-section" v-if="detail.records?.length">
            <template #header><h3>📝 答题记录</h3></template>
            <div v-for="(rec, idx) in detail.records" :key="rec.id || idx" class="record-item">
              <div class="record-header">
                <el-tag size="small" type="info">第 {{ rec.round_number }} 题</el-tag>
                <span class="record-score" :style="{ color: scoreColor(rec.score) }">
                  {{ rec.score ?? '-' }} 分
                </span>
              </div>
              <p class="record-q"><strong>问题：</strong>{{ rec.question }}</p>
              <p class="record-a"><strong>回答：</strong>{{ rec.answer }}</p>
              <p class="record-c" v-if="rec.comment"><strong>点评：</strong>{{ rec.comment }}</p>
            </div>
          </el-card>

          <el-card class="d-section">
            <template #header><h3>面试记录</h3></template>
            <el-descriptions :column="2" border size="small">
              <el-descriptions-item label="会话ID">{{ detail.session?.id }}</el-descriptions-item>
              <el-descriptions-item label="状态">{{ detail.session?.status }}</el-descriptions-item>
              <el-descriptions-item label="开始时间" v-if="detail.session?.start_time">{{ formatDate(detail.session.start_time) }}</el-descriptions-item>
              <el-descriptions-item label="结束时间" v-if="detail.session?.end_time">{{ formatDate(detail.session.end_time) }}</el-descriptions-item>
            </el-descriptions>
          </el-card>
        </template>
        <el-empty v-else-if="!detailLoading" description="暂无报告数据" />
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.candidate-page { max-width: 1200px; }

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-4);
}

.page-title {
  font-size: var(--font-size-xl);
  color: var(--color-text);
  margin: 0;
}

.filter-card { margin-bottom: var(--space-4); }

.pagination-wrap {
  display: flex;
  justify-content: center;
  margin-top: var(--space-6);
}

/* Detail dialog */
.dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}
.dialog-title {
  font-size: 18px;
  font-weight: 600;
}
.pass-select {
  width: 100px;
}
.pass-select :deep(.el-input__wrapper) {
  padding: 0 8px;
}
.pass-select :deep(.el-input__inner) {
  font-size: 13px;
}

.score-overview {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  padding: var(--space-5);
  margin-bottom: var(--space-4);
}

.score-circle {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 100px; min-width: 100px; height: 100px;
  border-radius: 50%;
  border: 5px solid currentColor;
  background: var(--color-surface);
  flex-shrink: 0;
}

.score-num { font-size: 28px; font-weight: 800; }
.score-label { font-size: 12px; opacity: 0.7; }

.score-summary { color: var(--color-text-secondary); margin: var(--space-3) 0 0; line-height: 1.6; }

.d-section { margin-bottom: var(--space-3); }
.d-section h3 { margin: 0; font-size: 14px; }

.content-text { white-space: pre-wrap; line-height: 1.8; color: var(--color-text-secondary); }

.record-item {
  padding: var(--space-4);
  background: var(--color-bg-alt);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-3);
}
.record-item:last-child { margin-bottom: 0; }
.record-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--space-3); }
.record-score { font-weight: 700; }
.record-q, .record-a, .record-c { margin: var(--space-2) 0; font-size: var(--font-size-sm); line-height: 1.6; }
.record-a { color: var(--color-text); }
.record-q, .record-c { color: var(--color-text-secondary); }
</style>
