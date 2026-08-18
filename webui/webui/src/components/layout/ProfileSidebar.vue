<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { UserFilled, Upload, DataAnalysis } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()

const menuItems = [
  { path: '/profile', title: '个人信息', icon: UserFilled },
  { path: '/resume', title: '简历上传', icon: Upload },
  { path: '/interview/sessions', title: '面试记录', icon: DataAnalysis },
]

const activePath = computed(() => {
  const p = route.path
  if (p.startsWith('/interview/sessions')) return '/interview/sessions'
  if (p.startsWith('/resume')) return '/resume'
  return '/profile'
})

function go(path) {
  if (path !== activePath.value) router.push(path)
}
</script>

<template>
  <aside class="ctx-sidebar">
    <div class="sidebar-heading">个人中心</div>
    <el-menu :default-active="activePath" class="ctx-menu" :collapse="false">
      <el-menu-item v-for="item in menuItems" :key="item.path" :index="item.path" @click="go(item.path)">
        <el-icon><component :is="item.icon" /></el-icon>
        <span>{{ item.title }}</span>
      </el-menu-item>
    </el-menu>
  </aside>
</template>

<style scoped>
.ctx-sidebar {
  width: 200px;
  min-width: 200px;
  background: var(--sidebar-bg);
  border-right: 1px solid var(--sidebar-border);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  overflow-y: auto;
}

.sidebar-heading {
  padding: 20px 20px 10px;
  font-size: 11px;
  font-weight: 700;
  color: var(--color-text-muted);
  text-transform: none;
  letter-spacing: 0;
  flex-shrink: 0;
}

.ctx-menu {
  border-right: none !important;
  flex: 1;
  background: transparent !important;
}

.ctx-menu :deep(.el-menu-item) {
  margin: 2px 8px;
  border-radius: var(--radius-md);
  height: 42px;
  line-height: 42px;
  font-size: var(--font-size-sm);
  color: var(--sidebar-text);
  transition: all var(--transition-fast);
}

.ctx-menu :deep(.el-menu-item:hover) {
  color: var(--color-primary);
  background: var(--sidebar-bg-hover) !important;
}

.ctx-menu :deep(.el-menu-item.is-active) {
  color: var(--sidebar-text-active) !important;
  background: var(--sidebar-bg-active) !important;
  font-weight: 500;
}
</style>
