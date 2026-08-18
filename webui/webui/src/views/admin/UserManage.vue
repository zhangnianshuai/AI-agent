<script setup>
import { ref, reactive, onMounted } from 'vue'
import { listUsers, updateUserRole, updateUserStatus } from '@/api/admin'
import { ElMessage, ElMessageBox } from 'element-plus'

const users = ref([])
const total = ref(0)
const loading = ref(false)

const filters = reactive({
  role: '',
  status: '',
  page: 1,
  page_size: 10,
})

const roleDialogVisible = ref(false)
const roleTarget = ref(null)
const newRole = ref('')

const roles = [
  { label: '候选人', value: 'candidate' },
  { label: 'HR', value: 'hr' },
  { label: '管理员', value: 'admin' },
]

const statusOptions = [
  { label: '正常', value: 1 },
  { label: '禁用', value: 0 },
]

async function fetchUsers() {
  loading.value = true
  try {
    const params = { page: filters.page, page_size: filters.page_size }
    if (filters.role) params.role = filters.role
    if (filters.status !== '') params.status = filters.status
    const data = await listUsers(params)
    users.value = data.list || []
    total.value = data.total || 0
  } catch {
    // Handled by interceptor
  } finally {
    loading.value = false
  }
}

function handlePageChange(page) {
  filters.page = page
  fetchUsers()
}

function openRoleDialog(user) {
  roleTarget.value = user
  newRole.value = user.role
  roleDialogVisible.value = true
}

async function handleRoleChange() {
  if (!roleTarget.value || !newRole.value) return

  try {
    await ElMessageBox.confirm(
      `确定将用户 "${roleTarget.value.username}" 的角色从 "${getRoleLabel(roleTarget.value.role)}" 修改为 "${getRoleLabel(newRole.value)}"？`,
      '确认修改角色',
      { type: 'warning', confirmButtonText: '确定', cancelButtonText: '取消' }
    )
    await updateUserRole({
      user_id: roleTarget.value.id,
      role: newRole.value,
    })
    ElMessage.success('角色修改成功')
    roleDialogVisible.value = false
    fetchUsers()
  } catch {
    // Cancelled or error
  }
}

async function handleToggleStatus(row) {
  const isEnabled = row.status === 1
  const action = isEnabled ? '禁用' : '启用'
  try {
    await ElMessageBox.confirm(
      `确定要${action}用户 "${row.username}" 吗？${isEnabled ? '禁用后该用户将无法登录。' : ''}`,
      `确认${action}`,
      { type: 'warning', confirmButtonText: '确定', cancelButtonText: '取消' }
    )
    const newStatus = isEnabled ? 0 : 1
    await updateUserStatus({ user_id: row.id, status: newStatus })
    row.status = newStatus
    ElMessage.success(`用户已${action}`)
  } catch { /* cancelled */ }
}

function getRoleTag(role) {
  const map = { admin: 'danger', hr: 'warning', candidate: 'info' }
  return map[role] || 'info'
}

function getRoleLabel(role) {
  const map = { admin: '管理员', hr: 'HR', candidate: '候选人' }
  return map[role] || role
}

function formatDate(val) {
  if (!val) return '-'
  // 后端返回 "2026-07-12T02:52:40"，直接截取前 19 位替换 T 为空格
  const s = String(val)
  if (s.length >= 19) {
    return s.slice(0, 10) + ' ' + s.slice(11, 16)
  }
  return s
}

onMounted(() => {
  fetchUsers()
})
</script>

<template>
  <div class="user-manage">
    <div class="page-header">
      <h1 class="page-title">用户管理</h1>
      <span class="user-count">共 {{ total }} 个用户</span>
    </div>

    <!-- Filters -->
    <el-card class="filter-card">
      <el-form :model="filters" inline>
        <el-form-item label="角色">
          <el-select v-model="filters.role" placeholder="全部" clearable @change="fetchUsers" style="width: 130px">
            <el-option v-for="r in roles" :key="r.value" :label="r.label" :value="r.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" clearable @change="fetchUsers" style="width: 110px">
            <el-option v-for="s in statusOptions" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchUsers">查询</el-button>
          <el-button @click="filters.role = ''; filters.status = ''; fetchUsers()">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- User table -->
    <el-card class="table-card">
      <el-table :data="users" v-loading="loading" stripe :header-cell-style="{ background: '#f5f7fa', color: '#606266' }">
        <el-table-column prop="username" label="用户名" min-width="120" show-overflow-tooltip />
        <el-table-column prop="real_name" label="姓名" width="100" />
        <el-table-column prop="email" label="邮箱" min-width="180" show-overflow-tooltip />
        <el-table-column prop="phone" label="手机号" width="130" />
        <el-table-column label="注册时间" width="170">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="角色" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="getRoleTag(row.role)" size="small">
              {{ getRoleLabel(row.role) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'danger'" size="small">
              {{ row.status === 1 ? '正常' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right" align="center">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="openRoleDialog(row)">角色</el-button>
            <el-divider direction="vertical" />
            <el-button
              link
              size="small"
              :type="row.status === 1 ? 'danger' : 'success'"
              @click="handleToggleStatus(row)"
            >
              {{ row.status === 1 ? '封禁' : '解封' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrap" v-if="total > filters.page_size">
        <el-pagination
          v-model:current-page="filters.page"
          :page-size="filters.page_size"
          :total="total"
          background
          layout="total, prev, pager, next"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>

    <!-- Role change dialog -->
    <el-dialog v-model="roleDialogVisible" title="修改用户角色" width="420px">
      <div class="dialog-body" v-if="roleTarget">
        <p class="dialog-user">
          <span class="dialog-label">用户</span>
          <strong>{{ roleTarget.username }}</strong>
        </p>
        <p class="dialog-current">
          <span class="dialog-label">当前角色</span>
          <el-tag :type="getRoleTag(roleTarget.role)" size="small">{{ getRoleLabel(roleTarget.role) }}</el-tag>
        </p>
        <p class="dialog-new">
          <span class="dialog-label">新角色</span>
          <el-select v-model="newRole" placeholder="选择新角色" style="width: 200px">
            <el-option v-for="r in roles" :key="r.value" :label="r.label" :value="r.value" />
          </el-select>
        </p>
      </div>
      <template #footer>
        <el-button @click="roleDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleRoleChange">确认修改</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.user-manage {
  max-width: 1200px;
}

.page-header {
  display: flex;
  align-items: baseline;
  gap: var(--space-4);
  margin-bottom: var(--space-6);
}

.page-title {
  font-size: var(--font-size-2xl);
  margin: 0;
  color: var(--color-text);
}

.user-count {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.filter-card {
  margin-bottom: var(--space-4);
}

.table-card :deep(.el-table th) {
  font-weight: 600;
}

.pagination-wrap {
  display: flex;
  justify-content: center;
  margin-top: var(--space-6);
}

/* dialog */
.dialog-body p {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin: var(--space-3) 0;
}

.dialog-label {
  width: 70px;
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}
</style>
