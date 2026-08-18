<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import defaultAvatar from '@/assets/user/vue-color-avatar.png'
import { Search, ArrowDown, UserFilled, SwitchButton } from '@element-plus/icons-vue'
import { DotLottie } from '@lottiefiles/dotlottie-web'

const router = useRouter()
const auth = useAuthStore()

const searchKeyword = ref('')

// ── Logo Lottie ──
const logoCanvas = ref(null)
let logoLottie = null

onMounted(() => {
  if (logoCanvas.value) {
    logoLottie = new DotLottie({
      canvas: logoCanvas.value,
      src: '/Telegram logo.lottie',
      loop: true,
      autoplay: true,
    })
  }
})

onUnmounted(() => {
  if (logoLottie) {
    logoLottie.destroy()
    logoLottie = null
  }
})

function handleSearch() {
  router.push({
    path: '/jobs',
    query: { keyword: searchKeyword.value || undefined },
  })
}

function handleLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <header class="topbar">
    <!-- Left: Logo -->
    <div class="topbar-logo" @click="router.push('/')">
      <div class="logo-icon">
        <canvas ref="logoCanvas" width="36" height="36" class="logo-lottie" />
      </div>
      <span class="logo-text">AI 面试官</span>
    </div>

    <!-- Center: Search bar -->
    <div class="topbar-search">
      <el-input
        v-model="searchKeyword"
        placeholder="搜索职位..."
        clearable
        :prefix-icon="Search"
        size="large"
        class="search-input"
        @keyup.enter="handleSearch"
      />
      <el-button
        type="primary"
        size="large"
        :icon="Search"
        @click="handleSearch"
        class="search-btn"
      />
    </div>

    <!-- Right: User area -->
    <div class="topbar-right">
      <template v-if="auth.isLoggedIn">
        <el-dropdown trigger="click" placement="bottom-end">
          <button class="user-btn">
            <el-avatar
              :size="36"
              class="user-avatar"
              :src="auth.user?.avatar_url || defaultAvatar"
              @error="() => {}"
            >
              {{ (auth.user?.real_name || auth.user?.username || 'U').charAt(0).toUpperCase() }}
            </el-avatar>
            <span class="user-name">{{ auth.user?.real_name || auth.user?.username || '用户' }}</span>
            <el-icon class="user-arrow"><ArrowDown /></el-icon>
          </button>
          <template #dropdown>
            <div class="user-dropdown-hd">
              <el-tag
                :type="auth.isAdmin ? 'danger' : auth.isHR ? 'warning' : 'info'"
                size="small"
                effect="dark"
              >
                {{ auth.isAdmin ? '管理员' : auth.isHR ? 'HR' : '候选人' }}
              </el-tag>
            </div>
            <el-dropdown-item @click="router.push('/profile')">
              <el-icon><UserFilled /></el-icon> 个人中心
            </el-dropdown-item>
            <el-dropdown-item divided @click="handleLogout">
              <el-icon><SwitchButton /></el-icon> 退出登录
            </el-dropdown-item>
          </template>
        </el-dropdown>
      </template>
      <template v-else>
        <el-button type="primary" size="small" @click="router.push('/login')">登录</el-button>
        <el-button size="small" @click="router.push('/register')">注册</el-button>
      </template>
    </div>
  </header>
</template>

<style scoped>
.topbar {
  height: var(--header-height, 64px);
  min-height: var(--header-height, 64px);
  background: #fff;
  border-bottom: 1px solid #F3F4F6;
  display: flex;
  align-items: center;
  padding: 0 24px;
  flex-shrink: 0;
  z-index: var(--z-sticky, 200);
  position: sticky;
  top: 0;
  gap: 20px;
}

/* ── Logo ── */
.topbar-logo {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  flex-shrink: 0;
  user-select: none;
}

.logo-icon {
  display: flex;
  align-items: center;
}

.logo-lottie {
  width: 36px;
  height: 36px;
  border-radius: 8px;
}

.logo-text {
  font-size: 17px;
  font-weight: 700;
  color: #111827;
  white-space: nowrap;
  letter-spacing: -0.2px;
}

/* ── Search bar ── */
.topbar-search {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  justify-content: center;
  max-width: 480px;
  margin: 0 auto;
}

.search-input :deep(.el-input__wrapper) {
  box-shadow: none !important;
  height: 42px;
  border: 1px solid #D1D5DB !important;
}

.search-input :deep(.el-input__wrapper:hover) {
  border-color: #9CA3AF !important;
}

.search-input :deep(.el-input.is-focus .el-input__wrapper) {
  border-color: #3B82F6 !important;
}

.search-btn {
  height: 42px;
  flex-shrink: 0;
  border: 1px solid #D1D5DB !important;
}

/* ── Right user area ── */
.topbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.user-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 10px 4px 4px;
  border-radius: var(--radius-full);
  cursor: pointer;
  transition: background 0.2s ease;
  background: none;
  border: none;
  font-family: inherit;
}

.user-btn:hover {
  background: #F3F4F6;
}

.user-avatar {
  background: #3B82F6 !important;
  color: #fff;
  font-weight: 600;
  font-size: 14px;
  flex-shrink: 0;
}

.user-name {
  font-size: 14px;
  font-weight: 500;
  color: #111827;
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-arrow {
  font-size: 12px;
  color: #9CA3AF;
  transition: transform 0.2s ease;
}

.user-btn:hover .user-arrow {
  transform: rotate(180deg);
}

.user-dropdown-hd {
  padding: 8px 16px;
  text-align: center;
}

/* ── Responsive ── */
@media (max-width: 1024px) {
  .topbar {
    padding: 0 16px;
    gap: 12px;
  }

  .topbar-search {
    max-width: 320px;
  }
}

@media (max-width: 768px) {
  .topbar {
    padding: 0 12px;
  }

  .topbar-search {
    max-width: 200px;
  }

  .logo-text { font-size: 15px; }
  .user-name { display: none; }
}
</style>
