<script setup>
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { UserFilled, Setting } from '@element-plus/icons-vue'

const router = useRouter()
const auth = useAuthStore()

const cards = [
  {
    title: '用户管理',
    desc: '管理系统用户账号、角色权限和状态',
    icon: UserFilled,
    path: '/admin/users',
    roles: ['admin'],
  },
  {
    title: 'Agent 面试官配置',
    desc: '配置 AI 面试官的模型参数、题目数量和评分标准',
    icon: Setting,
    path: '/admin/configs',
    roles: ['admin', 'hr'],
  },
].filter(c => c.roles.includes(auth.role))

function go(path) {
  router.push(path)
}
</script>

<template>
  <div class="admin-home">
    <div class="admin-header">
      <h1>管理后台</h1>
      <p>系统管理与配置</p>
    </div>

    <div class="admin-cards">
      <div
        v-for="card in cards"
        :key="card.path"
        class="admin-card"
        @click="go(card.path)"
      >
        <div class="card-icon">
          <el-icon :size="32"><component :is="card.icon" /></el-icon>
        </div>
        <div class="card-body">
          <h3>{{ card.title }}</h3>
          <p>{{ card.desc }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.admin-home {
  max-width: 800px;
  margin: 0 auto;
  padding: 40px 24px;
}

.admin-header {
  margin-bottom: 32px;
}

.admin-header h1 {
  font-size: 24px;
  font-weight: 700;
  color: #111827;
  margin: 0 0 8px;
}

.admin-header p {
  font-size: 14px;
  color: #6B7280;
  margin: 0;
}

.admin-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.admin-card {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 24px;
  background: #FFFFFF;
  border: 1px solid #E5E7EB;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.admin-card:hover {
  border-color: #3B82F6;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.1);
  transform: translateY(-2px);
}

.card-icon {
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(59, 130, 246, 0.08);
  color: #3B82F6;
  border-radius: 8px;
  flex-shrink: 0;
}

.card-body h3 {
  font-size: 16px;
  font-weight: 600;
  color: #111827;
  margin: 0 0 6px;
}

.card-body p {
  font-size: 13px;
  color: #6B7280;
  margin: 0;
  line-height: 1.5;
}
</style>
