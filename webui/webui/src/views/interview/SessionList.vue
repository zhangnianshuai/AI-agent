<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { listInterviewSessions, deleteInterviewSession } from '@/api/interview'
import { formatDate } from '@/utils'
import { ElMessage, ElMessageBox } from 'element-plus'
import { DataAnalysis, View, Delete } from '@element-plus/icons-vue'

const router = useRouter()
const sessions = ref([])
const loading = ref(true)
const deleting = ref(null)  // track which session is being deleted
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)

async function fetchSessions() {
  loading.value = true
  try {
    const data = await listInterviewSessions()
    sessions.value = data.items || data.list || data || []
    total.value = data.total || sessions.value.length
  } catch {
    sessions.value = []
  } finally {
    loading.value = false
  }
}

function scoreColor(score) {
  if (!score) return '#94a3b8'
  if (score >= 80) return '#10b981'
  if (score >= 60) return '#f59e0b'
  return '#ef4444'
}

function statusType(status) {
  if (status === 'completed') return 'success'
  if (status === 'cancelled') return 'danger'
  return 'info'
}

function statusLabel(status) {
  const map = { completed: '已完成', cancelled: '已取消', in_progress: '进行中' }
  return map[status] || status || '未知'
}

function viewReport(sessionId) {
  const id = sessionId
  if (!id || id === 'undefined' || id === 'null') return
  router.push(`/interview/report/${id}`)
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm('确定删除该面试记录吗？将同时删除答题记录和评价。', '确认删除', {
      type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消',
    })
    deleting.value = row.id
    await deleteInterviewSession(row.id)
    ElMessage.success('已删除')
    fetchSessions()
  } catch { /* cancelled or error */ }
  finally { deleting.value = null }
}

onMounted(fetchSessions)
</script>

<template>
  <div class="session-list">
    <h1 class="page-title">
      <el-icon :size="24"><DataAnalysis /></el-icon>
      面试记录
    </h1>

    <el-card v-loading="loading">
      <el-table :data="sessions" stripe v-if="sessions.length">
        <el-table-column prop="id" label="会话ID" min-width="180" show-overflow-tooltip />
        <el-table-column prop="job_title" label="职位" min-width="140" show-overflow-tooltip />
        <el-table-column prop="company_name" label="公司" width="120" show-overflow-tooltip />
        <el-table-column label="总分" width="100" align="center">
          <template #default="{ row }">
            <span
              v-if="row.total_score !== undefined && row.total_score !== null"
              class="score-badge"
              :style="{ color: scoreColor(row.total_score), borderColor: scoreColor(row.total_score) }"
            >
              {{ row.total_score }}
            </span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="开始时间" width="160">
          <template #default="{ row }">
            {{ row.start_time ? formatDate(row.start_time) : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="结束时间" width="160">
          <template #default="{ row }">
            {{ row.end_time ? formatDate(row.end_time) : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right" align="center">
          <template #default="{ row }">
            <el-button
              type="primary"
              link
              :icon="View"
              @click="viewReport(row.id)"
            >
              详情
            </el-button>
            <el-button
              type="danger"
              link
              :icon="Delete"
              :loading="deleting === row.id"
              :disabled="deleting !== null && deleting !== row.id"
              @click="handleDelete(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-else-if="!loading" description="暂无面试记录">
        <el-button type="primary" @click="router.push('/jobs')">去浏览职位</el-button>
      </el-empty>
    </el-card>
  </div>
</template>

<style scoped>
.session-list {
  max-width: 1200px;
}

.page-title {
  font-size: 24px;
  margin: 0 0 24px;
  color: var(--color-text);
  display: flex;
  align-items: center;
  gap: 8px;
}

.score-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: 2px solid;
  font-weight: 700;
  font-size: 14px;
}

.text-muted {
  color: var(--color-text-muted, #94a3b8);
}
</style>
