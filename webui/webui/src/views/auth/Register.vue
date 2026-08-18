<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'
import { User, Lock, Message, Phone } from '@element-plus/icons-vue'

const router = useRouter()
const auth = useAuthStore()

const formRef = ref(null)
const form = reactive({
  username: '',
  password: '',
  confirmPassword: '',
  email: '',
  phone: '',
})

const validatePass = (rule, value, callback) => {
  if (value !== form.password) {
    callback(new Error('两次密码输入不一致'))
  } else {
    callback()
  }
}

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 5, max: 12, message: '用户名长度 5-12 个字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 20, message: '密码长度 6-20 个字符', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: validatePass, trigger: 'blur' },
  ],
}

const loading = ref(false)
const errorMsg = ref('')

async function handleRegister() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  errorMsg.value = ''
  try {
    await auth.register({
      username: form.username,
      password: form.password,
      email: form.email || undefined,
      phone: form.phone || undefined,
    })
    ElMessage.success('注册成功，请登录')
    router.push('/login')
  } catch (err) {
    errorMsg.value = err.message || '注册失败，请重试'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-page">
    <!-- Background decoration -->
    <div class="auth-bg">
      <div class="bg-blob bg-blob-1"></div>
      <div class="bg-blob bg-blob-2"></div>
      <div class="bg-grid"></div>
    </div>

    <div class="auth-wrapper">
      <!-- Left brand panel -->
      <div class="auth-brand">
        <div class="brand-content">
          <div class="brand-logo">
            <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
              <rect width="48" height="48" rx="14" fill="white" fill-opacity="0.15"/>
              <path d="M14 22L24 14L34 22V34C34 35 33 36 32 36H16C15 36 14 35 14 34V22Z" stroke="white" stroke-width="2" fill="none"/>
              <circle cx="24" cy="27" r="5" fill="white"/>
              <path d="M24 15V18M24 36V39M14 24H11M37 24H40" stroke="white" stroke-width="2" stroke-linecap="round" opacity="0.4"/>
            </svg>
          </div>
          <h2 class="brand-name">AI 面试官</h2>
          <p class="brand-desc">
            加入我们，开启 AI 赋能的求职之旅
          </p>
          <div class="brand-features">
            <div class="brand-feat">
              <div class="bf-check">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M2 7L5.5 10.5L12 3.5" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
              </div>
              <span>AI 智能简历解析</span>
            </div>
            <div class="brand-feat">
              <div class="bf-check">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M2 7L5.5 10.5L12 3.5" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
              </div>
              <span>真实模拟面试场景</span>
            </div>
            <div class="brand-feat">
              <div class="bf-check">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M2 7L5.5 10.5L12 3.5" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
              </div>
              <span>多维度评估报告</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Right form panel -->
      <div class="auth-form-panel">
        <div class="form-inner">
          <div class="form-header">
            <h1 class="form-title">创建账户</h1>
            <p class="form-sub">填写信息开始使用</p>
          </div>

          <el-form
            ref="formRef"
            :model="form"
            :rules="rules"
            label-position="top"
            @submit.prevent="handleRegister"
            class="auth-form"
          >
            <el-form-item label="用户名" prop="username">
              <el-input
                v-model="form.username"
                placeholder="5-12个字符"
                :prefix-icon="User"
                size="large"
                class="auth-input"
              />
            </el-form-item>

            <el-form-item label="密码" prop="password">
              <el-input
                v-model="form.password"
                type="password"
                placeholder="6-20个字符"
                :prefix-icon="Lock"
                size="large"
                show-password
                class="auth-input"
              />
            </el-form-item>

            <el-form-item label="确认密码" prop="confirmPassword">
              <el-input
                v-model="form.confirmPassword"
                type="password"
                placeholder="再次输入密码"
                :prefix-icon="Lock"
                size="large"
                show-password
                class="auth-input"
              />
            </el-form-item>

            <el-form-item label="邮箱（选填）" prop="email">
              <el-input
                v-model="form.email"
                placeholder="请输入邮箱"
                :prefix-icon="Message"
                size="large"
                class="auth-input"
              />
            </el-form-item>

            <el-form-item label="手机号（选填）" prop="phone">
              <el-input
                v-model="form.phone"
                placeholder="请输入手机号"
                :prefix-icon="Phone"
                size="large"
                class="auth-input"
              />
            </el-form-item>

            <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" class="auth-error-alert" />

            <el-button
              type="primary"
              size="large"
              :loading="loading"
              native-type="submit"
              class="auth-submit-btn"
            >
              {{ loading ? '注册中...' : '注册' }}
            </el-button>

            <div class="form-footer">
              已有账户？<router-link to="/login">立即登录</router-link>
            </div>
          </el-form>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  background: #FFFFFF;
}

/* Background */
.auth-bg {
  position: fixed;
  inset: 0;
  pointer-events: none;
}

.bg-blob {
  position: absolute;
  border-radius: 50%;
  filter: blur(120px);
  opacity: 0.1;
}

.bg-blob-1 {
  width: 500px; height: 500px;
  background: #3B82F6;
  top: -200px; right: -150px;
}

.bg-blob-2 {
  width: 400px; height: 400px;
  background: #60A5FA;
  bottom: -150px; left: -100px;
}

.bg-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(var(--color-border) 1px, transparent 1px),
    linear-gradient(90deg, var(--color-border) 1px, transparent 1px);
  background-size: 50px 50px;
  opacity: 0.3;
}

/* Wrapper */
.auth-wrapper {
  display: flex;
  width: 960px;
  max-width: calc(100% - 40px);
  min-height: 640px;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 24px rgba(0,0,0,0.06);
  position: relative;
  z-index: 1;
}

/* Brand panel */
.auth-brand {
  flex: 0 0 400px;
  background: linear-gradient(160deg, #3B82F6 0%, #2563EB 40%, #60A5FA 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-10);
  position: relative;
  overflow: hidden;
}

.auth-brand::before {
  content: '';
  position: absolute;
  inset: 0;
  background: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.03'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
  opacity: 0.4;
  pointer-events: none;
}

.brand-content {
  text-align: center;
  color: #fff;
  position: relative;
  z-index: 1;
}

.brand-logo {
  margin-bottom: var(--space-5);
  display: inline-block;
}

.brand-name {
  font-size: 28px;
  font-weight: 800;
  color: #fff;
  margin: 0 0 var(--space-3);
  letter-spacing: -0.5px;
}

.brand-desc {
  font-size: 15px;
  color: rgba(255,255,255,0.7);
  margin: 0 0 var(--space-8);
  line-height: 1.6;
}

.brand-features {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  text-align: left;
}

.brand-feat {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  font-size: 14px;
  color: rgba(255,255,255,0.85);
}

.bf-check {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: rgba(255,255,255,0.15);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

/* Form panel */
.auth-form-panel {
  flex: 1;
  background: var(--color-surface);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-8) var(--space-10);
  overflow-y: auto;
}

.form-inner {
  width: 100%;
  max-width: 360px;
}

.form-header {
  text-align: center;
  margin-bottom: var(--space-6);
}

.form-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--color-text);
  margin: 0 0 var(--space-1);
}

.form-sub {
  font-size: 14px;
  color: var(--color-text-muted);
  margin: 0;
}

/* Form */
.auth-form :deep(.el-form-item) {
  margin-bottom: 16px;
}

.auth-form :deep(.el-form-item__label) {
  font-weight: 500;
  font-size: 13px;
  padding-bottom: 2px;
}

.auth-input :deep(.el-input__wrapper) {
  border-radius: var(--radius-md);
  box-shadow: none;
}

.auth-submit-btn {
  width: 100%;
  height: 46px;
  font-size: 16px;
  font-weight: 600;
  border-radius: 6px;
  margin-top: var(--space-1);
  letter-spacing: 0.5px;
  background: #3B82F6 !important;
  border-color: #3B82F6 !important;
}

.auth-submit-btn:hover {
  background: #2563EB !important;
  border-color: #2563EB !important;
}

.form-footer {
  text-align: center;
  margin-top: var(--space-5);
  font-size: 14px;
  color: var(--color-text-muted);
}

.form-footer a {
  color: var(--color-primary);
  font-weight: 600;
  text-decoration: none;
}

.form-footer a:hover {
  color: var(--color-primary-dark);
}

/* Responsive */
@media (max-width: 768px) {
  .auth-wrapper {
    flex-direction: column;
    max-width: calc(100% - 32px);
    min-height: auto;
  }

  .auth-brand {
    flex: none;
    padding: var(--space-8) var(--space-6);
  }

  .brand-name { font-size: 22px; }
  .brand-desc { font-size: 13px; margin-bottom: var(--space-4); }
  .brand-features { display: none; }

  .auth-form-panel {
    padding: var(--space-6) var(--space-5);
  }

  .form-inner { max-width: 100%; }
}
.auth-error-alert { margin-bottom: var(--space-5); }
</style>
