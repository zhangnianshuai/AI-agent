<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { searchJobs, aiSearchJobs } from '@/api/job'
import { listPublicCompanies } from '@/api/company'
import { listInterviewSessions, deleteInterviewSession } from '@/api/interview'
import { formatDate, formatSalary } from '@/utils'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowRight,
  MagicStick,
  Delete,
  TrendCharts,
  Location,
} from '@element-plus/icons-vue'
import defaultLogo from '@/assets/company/default_company_image.png'

const router = useRouter()
const auth = useAuthStore()

const companies = ref([])
const totalJobCount = computed(() => companies.value.reduce((sum, c) => sum + (c.job_count || 0), 0))
const aiJobs = ref([])
const recentSessions = ref([])
const companiesLoading = ref(false)
const aiLoading = ref(false)
const sessionsLoading = ref(false)
const deleting = ref(null)

onMounted(async () => {
  // Fetch companies for left panel
  companiesLoading.value = true
  try {
    const data = await listPublicCompanies()
    companies.value = (data || []).slice(0, 10)
  } catch { /* not critical */ }
  finally { companiesLoading.value = false }

  if (auth.isLoggedIn) {
    fetchAISuggestions()
    fetchInterviewSessions()
  }
})

async function fetchInterviewSessions() {
  sessionsLoading.value = true
  try {
    const data = await listInterviewSessions()
    recentSessions.value = (data.items || data.list || data || []).slice(0, 7)
  } catch { /* silent */ }
  finally { sessionsLoading.value = false }
}

async function fetchAISuggestions() {
  aiLoading.value = true
  try {
    const data = await aiSearchJobs()
    aiJobs.value = (data?.items || data || []).slice(0, 6)
  } catch { aiJobs.value = [] }
  finally { aiLoading.value = false }
}

async function handleDeleteSession(row) {
  try {
    await ElMessageBox.confirm('确定删除该面试记录吗？', '确认删除', {
      type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消',
    })
    deleting.value = row.id
    await deleteInterviewSession(row.id)
    ElMessage.success('已删除')
    fetchInterviewSessions()
  } catch { /* cancelled */ }
  finally { deleting.value = null }
}

function goJobDetail(id) {
  router.push(`/jobs/${id}`)
}

function goCompanyDetail(id) {
  router.push(`/company/${id}`)
}

function goSessionReport(id) {
  if (id && id !== 'undefined') {
    router.push(`/interview/report/${id}`)
  }
}
</script>

<template>
  <div class="dashboard">
    <!-- ═══ LEFT PANEL: 公司列表 (25%) ═══ -->
    <aside class="dash-left">
      <div class="left-panel">
        <div class="left-header">
          <h2 class="left-title">入驻公司</h2>
          <router-link to="/jobs" class="left-view-all">浏览职位 &gt;&gt;&gt;</router-link>
        </div>

        <!-- Stats card -->
        <div class="left-stats" v-if="!companiesLoading">
          <div class="stats-item">
            <span class="stats-num">{{ companies.length }}</span>
            <span class="stats-label">入驻公司</span>
          </div>
          <div class="stats-divider"></div>
          <div class="stats-item">
            <span class="stats-num">{{ totalJobCount }}</span>
            <span class="stats-label">在招岗位</span>
          </div>
        </div>

        <div class="left-card" v-loading="companiesLoading">
          <template v-if="companies.length">
            <div
              v-for="c in companies"
              :key="c.id"
              class="left-company-item"
              @click="goCompanyDetail(c.id)"
            >
              <img
                :src="c.logo_url || defaultLogo"
                class="lci-logo"
                @error="e => e.target.src = defaultLogo"
              />
              <div class="lci-info">
                <div class="lci-name">{{ c.name }}</div>
                <div class="lci-meta">
                  <span v-if="c.scale" class="lci-scale">{{ c.scale }}</span>
                  <span v-if="c.address" class="lci-addr">
                    <el-icon :size="10"><Location /></el-icon>
                    {{ c.address }}
                  </span>
                </div>
              </div>
              <div class="lci-job-count">
                <span class="lci-count-num">{{ c.job_count || 0 }}</span>
                <span class="lci-count-label">个职位</span>
              </div>
            </div>
          </template>
          <el-empty v-else-if="!companiesLoading" description="暂无公司" :image-size="60" />
        </div>
      </div>
    </aside>

    <!-- ═══ RIGHT PANEL: 75% ═══ -->
    <main class="dash-right">
      <!-- Welcome -->
      <div class="welcome-card">
        <div class="welcome-left">
          <h1 class="welcome-name">{{ auth.user?.real_name || auth.user?.username || '你好' }}</h1>
          <p class="welcome-sub">{{ auth.isHR ? '管理您的公司与岗位' : '发现适合你的职位' }}</p>
        </div>
        <div class="welcome-right">
          <el-button class="welcome-btn" @click="router.push('/jobs')">
            浏览职位 <el-icon><ArrowRight /></el-icon>
          </el-button>
          <template v-if="auth.isHR">
            <el-button class="welcome-btn" @click="router.push('/companies')">
              公司管理 <el-icon><ArrowRight /></el-icon>
            </el-button>
            <el-button v-if="!auth.isAdmin" class="welcome-btn" @click="router.push('/admin/configs')">
              Agent 配置管理 <el-icon><ArrowRight /></el-icon>
            </el-button>
            <el-button v-if="auth.isAdmin" class="welcome-btn" @click="router.push('/admin')">
              管理后台 <el-icon><ArrowRight /></el-icon>
            </el-button>
          </template>
          <el-button v-if="auth.isLoggedIn && !auth.isHR" class="welcome-btn" @click="router.push('/resume')">
            上传简历 <el-icon><ArrowRight /></el-icon>
          </el-button>
          <el-button v-if="!auth.isLoggedIn" class="welcome-btn welcome-btn-primary" type="primary" @click="router.push('/register')">
            立即注册 <el-icon><ArrowRight /></el-icon>
          </el-button>
        </div>
      </div>

      <!-- Bottom: 6:4 split -->
      <div class="bottom-split">
        <!-- Left: AI 智能推荐 (62%) -->
        <div class="split-left">
          <h3 class="split-title">AI 智能推荐</h3>
          <div class="split-card" v-loading="aiLoading">
            <template v-if="auth.isLoggedIn">
              <template v-if="aiJobs.length">
                <div
                  v-for="job in aiJobs"
                  :key="job.job_id"
                  class="ai-job-item"
                  @click="goJobDetail(job.job_id)"
                >
                  <div class="ai-item-top">
                    <img
                      :src="job.company_logo || defaultLogo"
                      class="ai-item-logo"
                      @error="e => e.target.src = defaultLogo"
                    />
                    <div class="ai-item-main">
                      <span class="ai-item-title">{{ job.title }}</span>
                      <span class="ai-item-salary">{{ formatSalary(job.salary_min, job.salary_max) }}</span>
                    </div>
                  </div>
                  <div class="ai-item-bottom">
                    <span v-if="job.company_name" class="ai-item-company">{{ job.company_name }}</span>
                    <span v-if="job.location" class="ai-item-location">{{ job.location }}</span>
                    <span v-if="job.match_score" class="ai-item-match">
                      <span class="match-bar">
                        <span class="match-fill" :style="{ width: (job.match_score || 0) + '%' }"></span>
                      </span>
                      {{ job.match_score }}%
                    </span>
                  </div>
                </div>
              </template>
              <el-empty v-else-if="!aiLoading" description="暂无智能推荐" :image-size="48" />
            </template>
            <template v-else>
              <div class="guest-prompt">
                <el-icon :size="36"><MagicStick /></el-icon>
                <p>登录后开启 AI 智能推荐</p>
                <el-button type="primary" size="small" @click="router.push('/login')">立即登录</el-button>
              </div>
            </template>
          </div>
        </div>

        <!-- Right: 我的面试记录 (38%) -->
        <div class="split-right">
          <h3 class="split-title split-title-dual">我的面试记录</h3>
          <div class="split-card" v-loading="sessionsLoading">
            <template v-if="auth.isLoggedIn">
              <template v-if="recentSessions.length">
                <div
                  v-for="session in recentSessions"
                  :key="session.id"
                  class="session-item"
                  @click="goSessionReport(session.id)"
                >
                  <div class="session-left">
                    <div
                      :class="[
                        'session-dot',
                        session.status === 'completed' ? 'dot-green' : session.status === 'cancelled' ? 'dot-red' : 'dot-blue',
                      ]"
                    ></div>
                    <div class="session-info">
                      <div class="session-job">{{ session.job_title || '未知职位' }}</div>
                      <div class="session-meta">
                        <span>{{ session.start_time ? formatDate(session.start_time) : '-' }}</span>
                        <el-tag
                          :type="session.status === 'completed' ? 'success' : session.status === 'cancelled' ? 'danger' : 'info'"
                          size="small"
                          effect="plain"
                        >
                          {{ session.status === 'completed' ? '已完成' : session.status === 'cancelled' ? '已取消' : '进行中' }}
                        </el-tag>
                      </div>
                    </div>
                  </div>
                  <div class="session-right">
                    <span
                      v-if="session.total_score !== undefined && session.total_score !== null"
                      class="session-score"
                      :class="
                        session.total_score >= 80 ? 'score-high' : session.total_score >= 60 ? 'score-mid' : 'score-low'
                      "
                    >
                      {{ session.total_score }}<small>分</small>
                    </span>
                    <span v-else class="session-score session-no-score">-</span>
                    <el-button
                      type="danger"
                      link
                      :icon="Delete"
                      :loading="deleting === session.id"
                      :disabled="deleting !== null && deleting !== session.id"
                      @click.stop="handleDeleteSession(session)"
                      class="delete-btn"
                    />
                  </div>
                </div>
              </template>
              <el-empty v-else-if="!sessionsLoading" description="暂无面试记录" :image-size="48">
                <el-button type="primary" size="small" @click="router.push('/jobs')">去面试</el-button>
              </el-empty>
            </template>
            <template v-else>
              <div class="guest-prompt">
                <el-icon :size="36"><TrendCharts /></el-icon>
                <p>登录后查看面试记录</p>
                <el-button type="primary" size="small" @click="router.push('/login')">立即登录</el-button>
              </div>
            </template>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
.dashboard {
  display: flex;
  height: calc(100vh - var(--header-height, 64px));
  background: #F8FAFC;
  gap: 0;
  overflow: hidden;
}

/* ═══════════════════════════════════════════
   LEFT PANEL (25%)
   ═══════════════════════════════════════════ */
.dash-left {
  width: 25%;
  min-width: 260px;
  max-width: 320px;
  flex-shrink: 0;
  border-right: 1px solid #E8ECF1;
  background: #fff;
}

.left-panel {
  padding: 20px 16px;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.left-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  padding: 0 4px;
}

.left-title {
  font-size: 15px;
  font-weight: 700;
  color: #111827;
  margin: 0;
  padding-left: 10px;
  border-left: 3px solid #3B82F6;
}

.left-view-all {
  font-size: 12px;
  color: #3B82F6;
  text-decoration: none;
  font-weight: 500;
  white-space: nowrap;
}

.left-view-all:hover {
  color: #2563EB;
}

/* ── Stats card ── */
.left-stats {
  display: flex;
  align-items: center;
  padding: 10px 16px;
  margin-bottom: 10px;
  background: linear-gradient(135deg, #EFF6FF 0%, #F0F9FF 100%);
  border: 1px solid #BFDBFE;
  border-radius: 8px;
  flex-shrink: 0;
}

.stats-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1px;
}

.stats-num {
  font-size: 20px;
  font-weight: 800;
  color: #1D4ED8;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
}

.stats-label {
  font-size: 11px;
  color: #6B7280;
  font-weight: 500;
}

.stats-divider {
  width: 1px;
  height: 26px;
  background: #BFDBFE;
  flex-shrink: 0;
}

/* ── Card ── */
.left-card {
  flex: 1;
  background: #FFFFFF;
  border: 1px solid #E5E7EB;
  border-radius: 6px;
  overflow-y: auto;
  min-height: 0;
}

/* ── Company item ── */
.left-company-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-bottom: 1px solid #F3F4F6;
  cursor: pointer;
  transition: background 0.2s ease;
}

.left-company-item:last-child {
  border-bottom: none;
}

.left-company-item:hover {
  background: #F0F6FF;
}

.lci-logo {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  object-fit: cover;
  flex-shrink: 0;
  background: #F3F4F6;
  border: 1px solid #E5E7EB;
}

.lci-info {
  flex: 1;
  min-width: 0;
}

.lci-name {
  font-size: 14px;
  font-weight: 600;
  color: #111827;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-bottom: 3px;
}

.lci-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: #9CA3AF;
}

.lci-scale {
  color: #6B7280;
  background: #F3F4F6;
  padding: 1px 6px;
  border-radius: 3px;
  white-space: nowrap;
}

.lci-addr {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.lci-job-count {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
  gap: 1px;
}

.lci-count-num {
  font-size: 18px;
  font-weight: 700;
  color: #3B82F6;
  line-height: 1.1;
}

.lci-count-label {
  font-size: 10px;
  color: #9CA3AF;
}

/* ═══════════════════════════════════════════
   RIGHT PANEL (75%)
   ═══════════════════════════════════════════ */
.dash-right {
  flex: 1;
  min-width: 0;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  overflow: hidden;
}

/* ── Welcome ── */
.welcome-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  flex-shrink: 0;
  background: linear-gradient(135deg, #3B82F6 0%, #2563EB 100%);
  border-radius: 10px;
}

.welcome-name {
  font-size: 24px;
  font-weight: 700;
  color: #fff;
  margin: 0;
  letter-spacing: -0.5px;
}

.welcome-sub {
  font-size: 14px;
  color: rgba(255,255,255,0.8);
  margin: 4px 0 0;
}

.welcome-right {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-shrink: 0;
}

.welcome-btn {
  height: 34px;
  padding: 0 16px;
  font-size: 13px;
  font-weight: 500;
  color: #fff;
  background: rgba(255,255,255,0.15);
  border: 1px solid rgba(255,255,255,0.3);
  border-radius: 6px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  transition: all 0.15s ease;
}

.welcome-btn:hover {
  background: rgba(255,255,255,0.25);
  border-color: rgba(255,255,255,0.5);
  color: #fff;
}

.welcome-btn-primary {
  color: #2563EB;
  background: #fff;
  border-color: #fff;
}

.welcome-btn-primary:hover {
  background: #F0F6FF;
  border-color: #F0F6FF;
}

/* ── Bottom split ── */
.bottom-split {
  display: flex;
  gap: 20px;
  flex: 1;
  min-height: 0;
}

.split-left {
  flex: 0 0 62%;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.split-right {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.split-title {
  font-size: 15px;
  font-weight: 700;
  color: #111827;
  margin: 0 0 12px 0;
  flex-shrink: 0;
  padding-left: 10px;
  border-left: 3px solid #3B82F6;
}

.split-title-dual {
  font-weight: 700;
  border-left-color: #22C55E;
}

.title-light {
  font-weight: 400;
  color: #6B7280;
}

.split-card {
  flex: 1;
  background: #FFFFFF;
  border: 1px solid #E5E7EB;
  border-radius: 6px;
  min-height: 0;
}

/* ── AI recommend items ── */
.ai-job-item {
  padding: 14px 16px;
  border-bottom: 1px solid #F3F4F6;
  cursor: pointer;
  transition: background 0.2s ease;
}

.ai-job-item:last-child {
  border-bottom: none;
}

.ai-job-item:hover {
  background: #F9FAFB;
}

.ai-job-item:hover .ai-item-title {
  color: #3B82F6;
}

.ai-item-top {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 6px;
}

.ai-item-logo {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  object-fit: cover;
  flex-shrink: 0;
  background: #F3F4F6;
}

.ai-item-main {
  flex: 1;
  min-width: 0;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
}

.ai-item-title {
  font-size: 14px;
  font-weight: 600;
  color: #111827;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition: color 0.2s ease;
}

.ai-item-salary {
  font-size: 14px;
  font-weight: 700;
  color: #EF4444;
  white-space: nowrap;
  flex-shrink: 0;
}

.ai-item-bottom {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.ai-item-company {
  font-size: 12px;
  color: #6B7280;
}

.ai-item-location {
  font-size: 12px;
  color: #9CA3AF;
}

.ai-item-match {
  font-size: 12px;
  font-weight: 600;
  color: #3B82F6;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
}

.match-bar {
  width: 60px;
  height: 4px;
  background: #E5E7EB;
  border-radius: 2px;
  overflow: hidden;
}

.match-fill {
  height: 100%;
  background: #3B82F6;
  border-radius: 2px;
  transition: width 0.6s ease;
}

/* ── Session items ── */
.session-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid #F3F4F6;
  cursor: pointer;
  transition: background 0.2s ease;
  gap: 12px;
}

.session-item:last-child {
  border-bottom: none;
}

.session-item:hover {
  background: #F9FAFB;
}

.session-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  flex: 1;
}

.session-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot-green { background: #22C55E; }
.dot-red   { background: #EF4444; }
.dot-blue  { background: #3B82F6; }

.session-info {
  min-width: 0;
}

.session-job {
  font-size: 14px;
  font-weight: 600;
  color: #111827;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 3px;
  font-size: 12px;
  color: #9CA3AF;
}

.session-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.session-score {
  font-size: 20px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.session-score small {
  font-size: 12px;
  font-weight: 500;
  margin-left: 1px;
}

.score-high { color: #22C55E; }
.score-mid  { color: #F59E0B; }
.score-low  { color: #EF4444; }

.session-no-score {
  color: #D1D5DB;
}

.delete-btn {
  opacity: 0;
  transition: opacity 0.2s ease;
}

.session-item:hover .delete-btn {
  opacity: 1;
}

/* ── Guest prompt ── */
.guest-prompt {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px 16px;
  color: #9CA3AF;
  gap: 8px;
}

.guest-prompt p {
  margin: 4px 0;
  font-size: 14px;
  color: #6B7280;
}

/* ── Responsive ── */
@media (max-width: 1200px) {
  .dash-left {
    min-width: 220px;
    max-width: 260px;
  }

  .welcome-name { font-size: 22px; }
  .welcome-sub  { font-size: 13px; }
  .welcome-btn  { font-size: 12px; padding: 0 12px; }

  .bottom-split {
    flex-direction: column;
  }

  .split-left  { flex: none; max-height: 280px; }
  .split-right { flex: none; max-height: 280px; }
}

@media (max-width: 768px) {
  .dashboard {
    flex-direction: column;
    height: auto;
    min-height: calc(100vh - var(--header-height, 64px));
  }

  .dash-left {
    width: 100%;
    max-width: none;
    max-height: 35vh;
    border-right: none;
    border-bottom: 1px solid #E8ECF1;
    min-width: 0;
    overflow-y: auto;
  }

  .left-card { max-height: none; }

  .dash-right {
    padding: 14px;
    overflow-y: auto;
    flex: 1;
  }

  .welcome-card {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
    padding: 16px;
  }

  .welcome-right { flex-wrap: wrap; width: 100%; }
  .welcome-name  { font-size: 20px; }
  .welcome-sub   { font-size: 13px; }
  .welcome-btn   { height: 32px; font-size: 12px; padding: 0 12px; }
}
</style>
