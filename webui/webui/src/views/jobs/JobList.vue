<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { searchJobs } from '@/api/job'
import { formatSalary } from '@/utils'
import { Location, Search } from '@element-plus/icons-vue'
import defaultLogo from '@/assets/company/default_company_image.png'

const router = useRouter()
const route = useRoute()

const jobs = ref([])
const total = ref(0)
const loading = ref(false)

const filters = reactive({
  keyword: '',
  location: '',
  category: '',
  page: 1,
  page_size: 5,
})

async function fetchJobs() {
  loading.value = true
  try {
    const params = {}
    if (filters.keyword) params.keyword = filters.keyword
    if (filters.location) params.location = filters.location
    if (filters.category && filters.category !== '全部') params.category = filters.category
    params.page = filters.page
    params.page_size = filters.page_size

    const data = await searchJobs(params)
    jobs.value = data.items || []
    total.value = data.total || 0
  } catch {
    // Error handled by interceptor
  } finally {
    loading.value = false
  }
}

function applyQueryParams() {
  const q = route.query
  filters.keyword = q.keyword || ''
  filters.category = q.category || ''
  filters.location = q.location || ''
  filters.page = 1
  fetchJobs()
}

function handlePageChange(page) {
  filters.page = page
  fetchJobs()
}

function goDetail(id) {
  router.push(`/jobs/${id}`)
}

onMounted(() => {
  applyQueryParams()
})

watch(() => route.query, () => {
  applyQueryParams()
})
</script>

<template>
  <div class="job-list">
    <!-- Page header -->
    <div class="page-header">
      <h1 class="page-title">职位浏览</h1>
    </div>


    <!-- Filters -->
    <div class="filter-bar">
      <el-input
        v-model="filters.keyword"
        placeholder="搜索关键词"
        clearable
        :prefix-icon="Search"
        class="filter-input"
        @keyup.enter="fetchJobs"
        @clear="fetchJobs"
      />
      <el-select
        v-model="filters.category"
        placeholder="职位类别"
        clearable
        class="filter-select"
        @change="fetchJobs"
      >
        <el-option label="技术" value="技术" />
        <el-option label="产品" value="产品" />
        <el-option label="设计" value="设计" />
        <el-option label="运营" value="运营" />
        <el-option label="市场" value="市场" />
        <el-option label="销售" value="销售" />
        <el-option label="财务" value="财务" />
        <el-option label="人事" value="人事" />
        <el-option label="行政" value="行政" />
      </el-select>
      <el-input
        v-model="filters.location"
        placeholder="工作地点"
        clearable
        class="filter-input filter-input-loc"
        @keyup.enter="fetchJobs"
        @clear="fetchJobs"
      />
      <span class="results-count">共 <strong>{{ total }}</strong> 个职位</span>
    </div>

    <div v-loading="loading" class="job-cards">
      <transition-group name="job-list-fade" tag="div" class="cards-grid" v-if="jobs.length">
        <div
          v-for="job in jobs"
          :key="job.job_id"
          class="job-card-item"
          @click="goDetail(job.job_id)"
        >
          <!-- Top row: title | salary -->
          <div class="jci-row jci-row-top">
            <h3 class="jci-title">
              {{ job.title }}
              <el-tag v-if="job.status === 2" size="small" type="danger" effect="plain" class="jci-status-tag">已下架</el-tag>
            </h3>
            <div class="jci-salary">
              {{ formatSalary(job.salary_min, job.salary_max) }}
            </div>
          </div>
          <!-- Bottom row: logo+company | category -->
          <div class="jci-row jci-row-bottom">
            <div class="jci-company" v-if="job.company_name">
              <img
                :src="job.company_logo || defaultLogo"
                class="jci-logo-inline"
                @error="e => e.target.src = defaultLogo"
              />
              <span class="jci-company-name">{{ job.company_name }}</span>
            </div>
            <div class="jci-category" v-if="job.category">
              <span class="jci-category-tag">{{ job.category }}</span>
            </div>
          </div>
          <!-- Extra info row -->
          <div class="jci-extra" v-if="job.location || job.education_requirement || job.experience_requirement">
            <span v-if="job.location" class="jci-tag">
              <el-icon :size="12"><Location /></el-icon>
              {{ job.location }}
            </span>
            <span v-if="job.education_requirement" class="jci-tag">{{ job.education_requirement }}</span>
            <span v-if="job.experience_requirement" class="jci-tag">{{ job.experience_requirement }}</span>
          </div>
        </div>
      </transition-group>

      <el-empty v-else-if="!loading" description="暂无匹配的职位" :image-size="80">
        <el-button type="primary" @click="router.push('/')">返回首页</el-button>
      </el-empty>

      <div class="pagination-wrap" v-if="total > filters.page_size">
        <el-pagination
          v-model:current-page="filters.page"
          :page-size="filters.page_size"
          :total="total"
          background
          layout="prev, pager, next"
          @current-change="handlePageChange"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.job-list {
  width: 100%;
}

/* Page header */
.page-header {
  margin-bottom: var(--space-5);
}

.page-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--color-text);
  margin: 0;
  letter-spacing: -0.5px;
}

/* Filter bar */
.filter-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: var(--space-5);
  flex-wrap: wrap;
}

.filter-input {
  width: 220px;
}

.filter-input-loc {
  width: 160px;
}

.filter-select {
  width: 130px;
}

.results-count {
  font-size: 13px;
  color: var(--color-text-muted);
  margin-left: auto;
  white-space: nowrap;
}

.results-count strong {
  color: var(--color-text);
}

/* Job cards */
.cards-grid {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.job-card-item {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--space-5);
  cursor: pointer;
  transition: all 0.25s ease;
}

.job-card-item:hover {
  border-color: var(--color-primary);
  box-shadow: 0 4px 20px rgba(59,130,246,0.06);
  transform: translateY(-1px);
}

/* Two-row layout */
.jci-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.jci-row-top {
  margin-bottom: var(--space-2);
}

.jci-row-bottom {
  margin-bottom: var(--space-2);
}

/* Title — bold, top-left */
.jci-title {
  font-size: 17px;
  font-weight: 700;
  color: var(--color-text);
  margin: 0;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex: 1;
  min-width: 0;
}

.jci-status-tag {
  flex-shrink: 0;
}

/* Company — logo + name, bottom-left */
.jci-company {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--color-text-muted);
}

.jci-logo-inline {
  width: 18px;
  height: 18px;
  border-radius: 3px;
  object-fit: cover;
  flex-shrink: 0;
}

.jci-company-name {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Salary — red, top-right */
.jci-salary {
  font-size: 20px;
  font-weight: 700;
  color: #ef4444;
  white-space: nowrap;
  flex-shrink: 0;
  margin-left: var(--space-4);
}

/* Category — bottom-right */
.jci-category {
  flex-shrink: 0;
  margin-left: var(--space-4);
}

.jci-category-tag {
  display: inline-block;
  padding: 2px 12px;
  border-radius: var(--radius-full);
  background: var(--color-primary-bg);
  color: var(--color-primary);
  font-size: 12px;
  font-weight: 500;
}

/* Extra info row */
.jci-extra {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  padding-top: var(--space-2);
  border-top: 1px solid var(--color-border-light, #f0f0f0);
}

.jci-tag {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 10px;
  border-radius: var(--radius-full);
  background: var(--color-bg-alt);
  color: var(--color-text-secondary);
  font-size: 12px;
  font-weight: 500;
}

/* Pagination */
.pagination-wrap {
  display: flex;
  justify-content: center;
  margin-top: var(--space-6);
}

/* Transition */
.job-list-fade-enter-active {
  transition: all 0.4s ease;
}
.job-list-fade-leave-active {
  transition: all 0.2s ease;
}
.job-list-fade-enter-from {
  opacity: 0;
  transform: translateY(12px);
}
.job-list-fade-leave-to {
  opacity: 0;
}

/* Responsive */
@media (max-width: 768px) {
  .page-title { font-size: 22px; }

  .filter-bar {
    gap: 8px;
  }

  .filter-input { width: 100%; }
  .filter-select { width: 100%; }
  .filter-input-loc { width: 100%; }

  .results-count {
    margin-left: 0;
    width: 100%;
  }

  .jci-row-top {
    flex-wrap: wrap;
  }

  .jci-salary {
    width: 100%;
    text-align: left;
    margin-left: 0;
    font-size: 16px;
    margin-top: 4px;
  }

  .jci-row-bottom {
    flex-wrap: wrap;
  }

  .jci-category {
    margin-left: 0;
    margin-top: 4px;
  }

  .jci-extra {
    flex-direction: column;
    gap: var(--space-2);
  }
}
</style>
