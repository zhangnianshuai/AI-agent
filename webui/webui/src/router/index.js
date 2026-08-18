import { createRouter, createWebHistory } from 'vue-router'
import { getToken } from '@/utils'

const routes = [
  // ═══════════════════════════════════════════
  // Full-page (no top bar / sidebar)
  // ═══════════════════════════════════════════
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/auth/Login.vue'),
    meta: { public: true, layout: 'none' },
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/auth/Register.vue'),
    meta: { public: true, layout: 'none' },
  },

  // ═══════════════════════════════════════════
  // Top bar only
  // ═══════════════════════════════════════════
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('@/views/dashboard/Dashboard.vue'),
    meta: { layout: 'dashboard' },
  },
  {
    path: '/jobs',
    name: 'JobList',
    component: () => import('@/views/jobs/JobList.vue'),
    meta: { public: true, layout: 'topbar' },
  },
  {
    path: '/jobs/:id',
    name: 'JobDetail',
    component: () => import('@/views/jobs/JobDetail.vue'),
    meta: { public: true, layout: 'topbar' },
  },
  {
    path: '/companies',
    name: 'CompanyList',
    component: () => import('@/views/company/CompanyList.vue'),
    meta: { roles: ['hr', 'admin'], layout: 'topbar' },
  },
  {
    path: '/companies/create',
    name: 'CompanyCreate',
    component: () => import('@/views/company/CompanyCreate.vue'),
    meta: { roles: ['hr', 'admin'], layout: 'topbar' },
  },
  {
    path: '/admin',
    name: 'AdminHome',
    component: () => import('@/views/admin/AdminHome.vue'),
    meta: { roles: ['admin', 'hr'], layout: 'topbar' },
  },
  {
    path: '/admin/users',
    name: 'UserManage',
    component: () => import('@/views/admin/UserManage.vue'),
    meta: { roles: ['admin'], layout: 'topbar' },
  },
  {
    path: '/admin/configs',
    name: 'AgentConfig',
    component: () => import('@/views/admin/AgentConfig.vue'),
    meta: { roles: ['admin', 'hr'], layout: 'topbar' },
  },
  {
    path: '/interview/:jobId',
    name: 'InterviewRoom',
    component: () => import('@/views/interview/InterviewRoom.vue'),
    meta: { layout: 'topbar' },
  },
  {
    path: '/interview/voice/:jobId',
    name: 'VoiceInterviewRoom',
    component: () => import('@/views/interview/VoiceInterviewRoom.vue'),
    meta: { layout: 'topbar' },
  },
  {
    path: '/interview/report/:sessionId',
    name: 'InterviewReport',
    component: () => import('@/views/interview/InterviewReport.vue'),
    meta: { layout: 'topbar' },
  },

  // ═══════════════════════════════════════════
  // Company sidebar (contextual)
  // ═══════════════════════════════════════════
  {
    path: '/companies/:id',
    name: 'CompanyDetail',
    component: () => import('@/views/company/CompanyDetail.vue'),
    meta: { roles: ['hr', 'admin'], layout: 'company' },
  },
  // 候选人查看公司详情（无侧边栏）
  {
    path: '/company/:id',
    name: 'CompanyPublic',
    component: () => import('@/views/company/CompanyDetail.vue'),
    meta: { roles: ['candidate', 'hr', 'admin'] },
  },
  {
    path: '/companies/:id/jobs',
    name: 'CompanyJobs',
    component: () => import('@/views/company/CompanyJobs.vue'),
    meta: { roles: ['hr', 'admin'], layout: 'company' },
  },
  {
    path: '/companies/:id/jobs/create',
    name: 'CompanyJobCreate',
    component: () => import('@/views/company/CompanyJobsCreate.vue'),
    meta: { roles: ['hr', 'admin'], layout: 'company' },
  },
  {
    path: '/companies/:id/questions',
    name: 'CompanyQuestions',
    component: () => import('@/views/company/CompanyQuestionBank.vue'),
    meta: { roles: ['hr', 'admin'], layout: 'company' },
  },
  {
    path: '/companies/:id/questions/:jobId',
    name: 'CompanyQuestionList',
    component: () => import('@/views/question/QuestionBankQuestions.vue'),
    meta: { roles: ['hr', 'admin'], layout: 'company' },
  },
  {
    path: '/companies/:id/candidates',
    name: 'CompanyCandidates',
    component: () => import('@/views/company/CompanyCandidates.vue'),
    meta: { roles: ['hr', 'admin'], layout: 'company' },
  },

  // ═══════════════════════════════════════════
  // Profile sidebar (contextual)
  // ═══════════════════════════════════════════
  {
    path: '/profile',
    name: 'Profile',
    component: () => import('@/views/profile/Profile.vue'),
    meta: { layout: 'profile' },
  },
  {
    path: '/resume',
    name: 'ResumeUpload',
    component: () => import('@/views/resume/ResumeUpload.vue'),
    meta: { layout: 'profile' },
  },
  {
    path: '/resume/view',
    name: 'ResumeView',
    component: () => import('@/views/resume/ResumeView.vue'),
    meta: { layout: 'profile' },
  },
  {
    path: '/interview/sessions',
    name: 'InterviewSessions',
    component: () => import('@/views/interview/SessionList.vue'),
    meta: { layout: 'profile' },
  },
]

// ── Redirect old routes ──
const redirects = [
  { path: '/questions', redirect: '/companies' },
  { path: '/questions/:companyId', redirect: to => `/companies/${to.params.companyId}/questions` },
  { path: '/questions/:companyId/:jobId', redirect: to => `/companies/${to.params.companyId}/questions/${to.params.jobId}` },
  { path: '/company/create', redirect: '/companies/create' },
  { path: '/jobs/create', redirect: '/companies' },
  { path: '/jobs/:id/questions', redirect: to => `/companies/${to.params.id.replace(/[^0-9]/g, '')}/questions` },
  { path: '/resume/view', redirect: '/profile' },
]
routes.push(...redirects)

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// Navigation guard
router.beforeEach(async (to, from, next) => {
  const token = getToken()

  // Public routes — allow access
  if (to.meta.public) {
    return next()
  }

  // Not logged in — redirect to login
  if (!token) {
    return next('/login')
  }

  // Fetch user info for ALL authenticated routes
  const { useAuthStore } = await import('@/stores/auth')
  const auth = useAuthStore()

  if (!auth.user) {
    try {
      await auth.fetchUser()
    } catch {
      // fetchUser already calls logout() internally on failure
      return next('/login')
    }
  }

  // Check role-based access
  if (to.meta.roles && !to.meta.roles.includes(auth.role)) {
    return next('/')
  }

  next()
})

export default router
