<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { searchJobs, updateJob, onlineJob, offlineJob, deleteJob, createJob } from '@/api/job'
import { formatSalary } from '@/utils'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Edit, Delete, CirclePlus } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const companyId = route.params.id

const jobs = ref([])
const total = ref(0)
const loading = ref(true)
const page = ref(1)
const pageSize = ref(10)

// Create / Edit dialog
const dialogVisible = ref(false)
const saving = ref(false)
const isEdit = ref(false)
const form = reactive({
  job_id: null,
  title: '',
  description: '',
  salary_min: null,
  salary_max: null,
  location: '',
  category: '',
  education_requirement: '',
  experience_requirement: '',
  headcount: 1,
})

const categories = ['技术', '产品', '设计', '运营', '市场', '销售', '财务', '人事', '行政']
const educations = ['不限', '高中', '大专', '本科', '硕士', '博士']
const experiences = ['不限', '应届生', '1-3年', '3-5年', '5-10年', '10年以上']

async function fetchJobs() {
  loading.value = true
  try {
    const data = await searchJobs({ company_id: companyId, page: page.value, page_size: pageSize.value })
    jobs.value = data.items || []
    total.value = data.total || 0
  } catch { jobs.value = [] }
  finally { loading.value = false }
}

function openCreate() {
  form.job_id = null
  form.title = ''
  form.description = ''
  form.salary_min = null
  form.salary_max = null
  form.location = ''
  form.category = ''
  form.education_requirement = ''
  form.experience_requirement = ''
  form.headcount = 1
  isEdit.value = false
  dialogVisible.value = true
}

function openEdit(job) {
  form.job_id = job.job_id
  form.title = job.title
  form.description = job.description || ''
  form.salary_min = job.salary_min
  form.salary_max = job.salary_max
  form.location = job.location || ''
  form.category = job.category || ''
  form.education_requirement = job.education_requirement || ''
  form.experience_requirement = job.experience_requirement || ''
  form.headcount = job.headcount || 1
  isEdit.value = true
  dialogVisible.value = true
}

async function handleSave() {
  saving.value = true
  try {
    if (isEdit.value) {
      await updateJob(form.job_id, { ...form, company_id: companyId })
      ElMessage.success('岗位已更新')
    } else {
      await createJob({ ...form, company_id: companyId })
      ElMessage.success('岗位已创建')
    }
    dialogVisible.value = false
    fetchJobs()
  } catch { /* handled */ }
  finally { saving.value = false }
}

async function handleToggleStatus(job) {
  const isOnline = job.status === 1
  const action = isOnline ? '下架' : '上架'
  try {
    await ElMessageBox.confirm(`确定要${action}该职位吗？`, `确认${action}`, {
      type: 'warning', confirmButtonText: '确定', cancelButtonText: '取消',
    })
    if (isOnline) { await offlineJob(job.job_id); job.status = 2 }
    else { await onlineJob(job.job_id); job.status = 1 }
    ElMessage.success(`岗位已${action}`)
  } catch { /* cancelled */ }
}

async function handleDelete(job) {
  try {
    await ElMessageBox.confirm(
      '删除岗位将同时清除题库和岗位画像，不可恢复！确定继续？',
      '确认删除', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
    await deleteJob(job.job_id)
    ElMessage.success('岗位已删除')
    fetchJobs()
  } catch { /* cancelled */ }
}

onMounted(() => fetchJobs())
</script>

<template>
  <div class="company-jobs">
    <div class="page-header">
      <h2 class="page-title">岗位管理</h2>
      <el-button type="primary" :icon="Plus" @click="openCreate">创建岗位</el-button>
    </div>

    <el-card>
      <el-table :data="jobs" v-loading="loading" stripe>
        <el-table-column prop="title" label="岗位名称" min-width="160" show-overflow-tooltip />
        <el-table-column prop="location" label="地点" width="100" />
        <el-table-column prop="category" label="类别" width="90" />
        <el-table-column label="薪资" width="140">
          <template #default="{ row }">
            <span class="salary-text">{{ formatSalary(row.salary_min, row.salary_max) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'danger'" size="small">
              {{ row.status === 1 ? '上架' : '下架' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right" align="center">
          <template #default="{ row }">
            <el-button type="primary" link :icon="Edit" @click="openEdit(row)">编辑</el-button>
            <el-button
              link
              :icon="row.status === 1 ? Delete : CirclePlus"
              :type="row.status === 1 ? 'warning' : 'success'"
              @click="handleToggleStatus(row)"
            >
              {{ row.status === 1 ? '下架' : '上架' }}
            </el-button>
            <el-button type="danger" link :icon="Delete" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrap" v-if="total > pageSize">
        <el-pagination v-model:current-page="page" :page-size="pageSize" :total="total"
          background layout="prev, pager, next" @current-change="fetchJobs" />
      </div>
    </el-card>

    <!-- Create / Edit Dialog -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑岗位' : '创建岗位'" width="600px">
      <el-form :model="form" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="岗位名称">
              <el-input v-model="form.title" placeholder="如：前端开发工程师" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="工作地点">
              <el-input v-model="form.location" placeholder="如：北京" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="职位类别">
              <el-select v-model="form.category" style="width: 100%">
                <el-option v-for="c in categories" :key="c" :label="c" :value="c" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="招聘人数">
              <el-input-number v-model="form.headcount" :min="1" :max="999" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="最低薪资">
              <el-input-number v-model="form.salary_min" :min="0" :step="1000" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="最高薪资">
              <el-input-number v-model="form.salary_max" :min="0" :step="1000" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="学历要求">
              <el-select v-model="form.education_requirement" style="width: 100%">
                <el-option v-for="e in educations" :key="e" :label="e" :value="e === '不限' ? '' : e" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="经验要求">
              <el-select v-model="form.experience_requirement" style="width: 100%">
                <el-option v-for="e in experiences" :key="e" :label="e" :value="e === '不限' ? '' : e" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="职位描述">
          <el-input v-model="form.description" type="textarea" :rows="4" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">
          {{ isEdit ? '保存修改' : '创建岗位' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.company-jobs { max-width: 1100px; }

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-4);
}

.page-title {
  font-size: var(--font-size-xl);
  color: var(--color-text);
  margin: 0;
}

.salary-text {
  color: var(--color-danger);
  font-weight: 700;
}

.pagination-wrap {
  display: flex;
  justify-content: center;
  margin-top: var(--space-6);
}
</style>
