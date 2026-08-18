<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { searchJobs } from '@/api/job'
import { formatSalary } from '@/utils'
import { Right } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const companyId = route.params.id
const jobs = ref([])
const loading = ref(true)

onMounted(async () => {
  try {
    const data = await searchJobs({ company_id: companyId, page: 1, page_size: 100 })
    jobs.value = data.items || []
  } catch { jobs.value = [] }
  finally { loading.value = false }
})

function goQuestions(job) {
  router.push(`/companies/${companyId}/questions/${job.job_id}`)
}
</script>

<template>
  <div class="question-bank-jobs">
    <div class="page-header">
      <h2 class="page-title">题库管理</h2>
    </div>

    <el-card v-loading="loading">
      <template #header>
        <span>共 {{ jobs.length }} 个岗位 — 点击进入题库</span>
      </template>

      <el-table :data="jobs" stripe v-if="jobs.length" @row-click="goQuestions" style="cursor: pointer">
        <el-table-column prop="title" label="岗位名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="location" label="地点" width="100" />
        <el-table-column prop="category" label="类别" width="100" />
        <el-table-column label="薪资" width="140">
          <template #default="{ row }">
            <span class="salary-text">{{ formatSalary(row.salary_min, row.salary_max) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'danger'" size="small">
              {{ row.status === 1 ? '上架' : '下架' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column width="80" align="center">
          <template #default><el-icon><Right /></el-icon></template>
        </el-table-column>
      </el-table>

      <el-empty v-else description="该企业暂无岗位" />
    </el-card>
  </div>
</template>

<style scoped>
.question-bank-jobs { max-width: 1100px; }

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

.salary-text {
  color: var(--color-danger);
  font-weight: 700;
}
</style>
