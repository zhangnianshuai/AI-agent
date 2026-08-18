<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { getJobDetail } from '@/api/job'
import { formatSalary } from '@/utils'
import { ChatDotRound } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const job = ref(null)
const loading = ref(true)

async function fetchDetail() {
  const jobId = route.params.id
  if (!jobId) return
  loading.value = true
  try {
    job.value = await getJobDetail(jobId)
  } catch {
    // Error handled by interceptor
  } finally {
    loading.value = false
  }
}

async function ensureUser() {
  if (auth.isLoggedIn && !auth.user) {
    try { await auth.fetchUser() } catch { /* ignore */ }
  }
}

onMounted(() => {
  fetchDetail()
  ensureUser()
})
watch(() => route.params.id, fetchDetail)

function startInterview() {
  if (!auth.isLoggedIn) {
    router.push('/login')
    return
  }
  router.push(`/interview/${route.params.id}`)
}

function goToResume() {
  router.push('/resume')
}
</script>

<template>
  <div class="job-detail" v-loading="loading">
    <div v-if="job">
      <el-card class="detail-header">
        <div class="header-top">
          <div>
            <h1>{{ job.title }}</h1>
            <div class="header-tags">
              <el-tag v-if="job.category" type="success">{{ job.category }}</el-tag>
              <el-tag v-if="job.experience_requirement" type="warning">{{ job.experience_requirement }}</el-tag>
            </div>
          </div>
          <div class="header-salary">
            <span class="salary">{{ formatSalary(job.salary_min, job.salary_max) }}</span>
          </div>
        </div>
      </el-card>

      <el-card class="detail-section">
        <template #header><h3>职位信息</h3></template>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="工作地点">{{ job.location || '-' }}</el-descriptions-item>
          <el-descriptions-item label="学历要求">{{ job.education_requirement || '-' }}</el-descriptions-item>
          <el-descriptions-item label="工作经验">{{ job.experience_requirement || '-' }}</el-descriptions-item>
          <el-descriptions-item label="招聘人数">{{ job.headcount || '-' }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card class="detail-section">
        <template #header><h3>职位描述</h3></template>
        <div class="description" v-if="job.description">
          {{ job.description }}
        </div>
        <el-empty v-else description="暂无职位描述" :image-size="80" />
      </el-card>

      <el-card class="detail-section" v-if="job.company_name || job.company_id">
        <template #header>
          <div class="section-header">
            <h3>公司信息</h3>
            <el-button v-if="job.company_id" type="primary" link size="small" @click="router.push(`/company/${job.company_id}`)">
              查看公司详情 →
            </el-button>
          </div>
        </template>
        <div class="company-info">
          <p v-if="job.company_name"><strong>公司名称：</strong>{{ job.company_name }}</p>
          <p v-if="job.industry"><strong>行业：</strong>{{ job.industry }}</p>
          <p v-if="job.scale"><strong>规模：</strong>{{ job.scale }}</p>
          <p v-if="job.address"><strong>地址：</strong>{{ job.address }}</p>
        </div>
      </el-card>

      <!-- Actions -->
      <div class="actions">
        <el-button
          type="primary"
          size="large"
          :icon="ChatDotRound"
          @click="startInterview"
        >
          开始 AI 面试
        </el-button>
        <el-button size="large" @click="goToResume" v-if="auth.isLoggedIn">
          上传简历
        </el-button>
      </div>
    </div>

    <el-empty v-else-if="!loading" description="职位不存在" />
  </div>
</template>

<style scoped>
.job-detail {
  max-width: 800px;
}

.detail-header {
  margin-bottom: var(--space-4);
}

.header-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.header-top h1 {
  margin: 0 0 var(--space-3);
  font-size: var(--font-size-2xl);
  color: var(--color-text);
}

.header-tags {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.header-salary .salary {
  font-size: var(--font-size-2xl);
  font-weight: 700;
  color: var(--color-danger);
}

.detail-section {
  margin-bottom: var(--space-4);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.section-header h3,
.detail-section h3 {
  margin: 0;
  font-size: var(--font-size-base);
}

.description {
  white-space: pre-wrap;
  line-height: 1.8;
  color: var(--color-text-secondary);
}

.company-info p {
  margin: var(--space-2) 0;
  color: var(--color-text-secondary);
}

.actions {
  display: flex;
  gap: var(--space-3);
  margin-top: var(--space-2);
}
</style>
