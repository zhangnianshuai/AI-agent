<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { listCompanies } from '@/api/company'
import { Right } from '@element-plus/icons-vue'
import defaultLogo from '@/assets/company/default_company_image.png'

const router = useRouter()
const companies = ref([])
const loading = ref(true)

async function fetchCompanies() {
  loading.value = true
  try {
    companies.value = await listCompanies() || []
  } catch {
    companies.value = []
  } finally {
    loading.value = false
  }
}

function goDetail(company) {
  router.push(`/companies/${company.id}`)
}

onMounted(fetchCompanies)
</script>

<template>
  <div class="company-list">
    <div class="page-header">
      <h1 class="page-title">公司管理</h1>
      <el-button type="primary" @click="router.push('/companies/create')">创建公司</el-button>
    </div>

    <el-card v-loading="loading">
      <el-table :data="companies" stripe v-if="companies.length" @row-click="goDetail" style="cursor: pointer">
        <el-table-column label="公司名称" min-width="180">
          <template #default="{ row }">
            <div class="company-cell">
              <img
                :src="row.logo_url || defaultLogo"
                class="company-logo"
                @error="e => e.target.src = defaultLogo"
              />
              <span class="company-name">{{ row.name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="industry" label="行业" width="120" />
        <el-table-column prop="scale" label="规模" width="120" />
        <el-table-column prop="address" label="地址" min-width="150" show-overflow-tooltip />
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
              {{ row.status === 1 ? '正常' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column width="60" align="center">
          <template #default><el-icon><Right /></el-icon></template>
        </el-table-column>
      </el-table>

      <el-empty v-else-if="!loading" description="暂无公司数据">
        <el-button type="primary" @click="router.push('/companies/create')">创建第一家</el-button>
      </el-empty>
    </el-card>
  </div>
</template>

<style scoped>
.company-list {
  max-width: 1100px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-4);
}

.page-title {
  font-size: var(--font-size-2xl);
  color: var(--color-text);
  margin: 0;
}

.company-cell {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.company-logo {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  object-fit: cover;
  flex-shrink: 0;
  border: 1px solid var(--color-border);
}

.company-name {
  font-weight: 600;
  font-size: var(--font-size-base);
}
</style>
