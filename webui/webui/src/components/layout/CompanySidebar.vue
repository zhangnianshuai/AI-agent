<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { OfficeBuilding, List, Collection, UserFilled } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()

const companyId = computed(() => route.params.id || '')

const menuItems = computed(() => [
  { path: `/companies/${companyId.value}`, title: '公司信息', icon: OfficeBuilding },
  { path: `/companies/${companyId.value}/jobs`, title: '岗位管理', icon: List },
  { path: `/companies/${companyId.value}/questions`, title: '题库管理', icon: Collection },
  { path: `/companies/${companyId.value}/candidates`, title: '候选人管理', icon: UserFilled },
])

const activePath = computed(() => {
  const p = route.path
  const base = `/companies/${companyId.value}`
  if (p === base) return base
  if (p.startsWith(`${base}/jobs`)) return `${base}/jobs`
  if (p.startsWith(`${base}/questions`)) return `${base}/questions`
  if (p.startsWith(`${base}/candidates`)) return `${base}/candidates`
  return base
})

function go(path) {
  if (path && path !== activePath.value) {
    router.push(path)
  }
}
</script>

<template>
  <aside class="ctx-sidebar" v-if="companyId">
    <div class="sidebar-heading">公司管理</div>
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

/* Force dark menu styling */
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
