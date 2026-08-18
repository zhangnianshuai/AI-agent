<script setup>
import { ref, onMounted, reactive, computed } from 'vue'
import { listAgentConfigs, setupAgentConfig } from '@/api/agent'
import { listCompanies } from '@/api/company'
import { searchJobs } from '@/api/job'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'
import { Setting } from '@element-plus/icons-vue'

const auth = useAuthStore()
const configs = ref([])
const loading = ref(true)

const interviewConfigs = computed(() => configs.value.filter(c => c.type !== 'sql_admin'))
const sqlAdminConfigs = computed(() => configs.value.filter(c => c.type === 'sql_admin'))

// Create/Edit dialog
const dialogVisible = ref(false)
const saving = ref(false)
const formRef = ref(null)
const companies = ref([])
const jobs = ref([])
const jobsLoading = ref(false)
const selectedCompany = ref('')

const form = reactive({
  config_id: '',
  job_id: '',
  type: 'interview',
  model_name: 'deepseek-v4-flash',
  temperature: 0.7,
  max_tokens: 4096,
  system_prompt: '',
  ranker_params: 5,
  score_threshold: 0.7,
  question_nums: 10,
})

const isSqlAdmin = computed(() => form.type === 'sql_admin')

const rules = computed(() => {
  if (isSqlAdmin.value) return {}
  return { job_id: [{ required: true, message: '请选择职位', trigger: 'change' }] }
})

onMounted(async () => {
  try {
    configs.value = await listAgentConfigs()
  } catch {
    // Handled by interceptor
  } finally {
    loading.value = false
  }
})

async function fetchCompanies() {
  if (companies.value.length) return
  try {
    companies.value = await listCompanies() || []
  } catch { companies.value = [] }
}

async function onCompanyChange(companyId) {
  form.job_id = ''
  jobs.value = []
  if (!companyId) return
  jobsLoading.value = true
  try {
    const data = await searchJobs({ company_id: companyId, page: 1, page_size: 100 })
    jobs.value = data.items || []
  } catch { jobs.value = [] }
  finally { jobsLoading.value = false }
}

function openCreate() {
  form.config_id = ''
  form.type = 'interview'
  selectedCompany.value = ''
  jobs.value = []
  form.job_id = ''
  form.model_name = 'deepseek-v4-flash'
  form.temperature = 0.7
  form.max_tokens = 4096
  form.system_prompt = ''
  form.ranker_params = 5
  form.score_threshold = 0.7
  form.question_nums = 10
  fetchCompanies()
  dialogVisible.value = true
}

function openEdit(config) {
  form.config_id = config.id
  form.type = config.type || 'interview'
  form.job_id = config.job_id || ''
  form.model_name = config.model_name || 'deepseek-v4-flash'
  form.temperature = config.temperature ?? 0.7
  form.max_tokens = config.max_tokens || 4096
  form.system_prompt = config.system_prompt || ''
  form.ranker_params = config.ranker_params ?? 5
  form.score_threshold = config.score_threshold ?? 0.7
  form.question_nums = config.question_nums || 10
  selectedCompany.value = ''
  jobs.value = []
  dialogVisible.value = true
}

async function handleSave() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  saving.value = true
  try {
    await setupAgentConfig(form.job_id || 0, form.config_id || undefined, { ...form })
    ElMessage.success('配置保存成功')
    dialogVisible.value = false
    configs.value = await listAgentConfigs()
  } catch {
    // Handled by interceptor
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="agent-config">
    <div class="page-header">
      <h1 class="page-title">
        <el-icon :size="24"><Setting /></el-icon>
        Agent 配置管理
      </h1>
      <el-button type="primary" @click="openCreate">新增配置</el-button>
    </div>

    <!-- 面试 Agent 配置 -->
    <el-card v-loading="loading" class="section-card">
      <template #header>
        <span class="card-header-title">面试 Agent 配置</span>
      </template>
      <el-table :data="interviewConfigs" stripe v-if="interviewConfigs.length">
        <el-table-column prop="company_name" label="公司" width="140" show-overflow-tooltip />
        <el-table-column prop="job_title" label="岗位" width="160" show-overflow-tooltip />
        <el-table-column prop="model_name" label="模型" width="160" />
        <el-table-column prop="temperature" label="温度" width="80" />
        <el-table-column prop="max_tokens" label="最大Token" width="100" />
        <el-table-column prop="question_nums" label="题目数" width="80" />
        <el-table-column prop="score_threshold" label="及格线" width="80" />
        <el-table-column prop="ranker_params" label="排序K" width="80" />
        <el-table-column label="操作" fixed="right" width="100">
          <template #default="{ row }">
            <el-button type="primary" link @click="openEdit(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else-if="!loading" description="暂无面试Agent配置" />
    </el-card>

    <!-- SQL Admin Agent 配置（仅管理员可见） -->
    <el-card v-if="auth.isAdmin" v-loading="loading" class="section-card">
      <template #header>
        <span class="card-header-title">SQL 数据助手配置</span>
      </template>
      <el-table :data="sqlAdminConfigs" stripe v-if="sqlAdminConfigs.length">
        <el-table-column prop="id" label="配置ID" width="300" show-overflow-tooltip />
        <el-table-column prop="model_name" label="模型" width="160" />
        <el-table-column prop="temperature" label="温度" width="80" />
        <el-table-column prop="max_tokens" label="最大Token" width="100" />
        <el-table-column label="题目数" width="80">
          <template #default><span class="col-na">-</span></template>
        </el-table-column>
        <el-table-column label="及格线" width="80">
          <template #default><span class="col-na">-</span></template>
        </el-table-column>
        <el-table-column label="排序K" width="80">
          <template #default><span class="col-na">-</span></template>
        </el-table-column>
        <el-table-column label="操作" fixed="right" width="100">
          <template #default="{ row }">
            <el-button type="primary" link @click="openEdit(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else-if="!loading" description="暂无SQL数据助手配置" />
    </el-card>

    <!-- Create/Edit dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="form.config_id ? '编辑 Agent 配置' : '新增 Agent 配置'"
      width="600px"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px" label-position="right">
        <!-- Job selection (only for new interview configs) -->
        <template v-if="!form.config_id && !isSqlAdmin">
          <el-form-item label="所属公司">
            <el-select v-model="selectedCompany" placeholder="选择公司" style="width: 100%"
              @change="onCompanyChange" @focus="fetchCompanies">
              <el-option v-for="c in companies" :key="c.id" :label="c.name" :value="c.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="关联职位" prop="job_id">
            <el-select v-model="form.job_id" placeholder="先选择公司" style="width: 100%"
              :loading="jobsLoading" :disabled="!selectedCompany">
              <el-option v-for="j in jobs" :key="j.job_id"
                :label="`${j.title} — ${j.location || '地点不限'}`" :value="j.job_id">
                <span>{{ j.title }}</span>
                <span style="float: right; color: var(--color-text-muted); font-size: 12px">
                  {{ j.location || '地点不限' }}
                </span>
              </el-option>
            </el-select>
          </el-form-item>
        </template>

        <!-- Type display when editing -->
        <el-form-item v-if="form.config_id" label="配置类型">
          <el-tag :type="isSqlAdmin ? '' : 'success'" size="small">
            {{ isSqlAdmin ? 'SQL 数据助手' : '面试 Agent' }}
          </el-tag>
        </el-form-item>

        <el-form-item label="模型">
          <el-input v-model="form.model_name" placeholder="如: deepseek-v4-flash" />
        </el-form-item>
        <el-form-item label="温度">
          <el-input-number v-model="form.temperature" :min="0" :max="2" :step="0.1" :precision="2" />
        </el-form-item>
        <el-form-item label="最大Token">
          <el-input-number v-model="form.max_tokens" :min="100" :max="32768" :step="100" />
        </el-form-item>

        <!-- Interview-only fields -->
        <template v-if="!isSqlAdmin">
          <el-form-item label="抽题数">
            <el-input-number v-model="form.question_nums" :min="1" :max="50" />
          </el-form-item>
          <el-form-item label="及格分数">
            <el-input-number v-model="form.score_threshold" :min="0" :max="1" :step="0.05" :precision="2" />
          </el-form-item>
          <el-form-item label="排序参数K">
            <el-input-number v-model="form.ranker_params" :min="1" :max="200" />
          </el-form-item>
        </template>

        <el-form-item label="系统提示词">
          <el-input v-model="form.system_prompt" type="textarea" :rows="6"
            placeholder="自定义Agent的系统提示词..." />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.agent-config {
  max-width: 1200px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-4);
}

.page-title {
  font-size: var(--font-size-2xl);
  color: var(--color-text);
  margin: 0;
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.section-card {
  margin-bottom: 20px;
}

.card-header-title {
  font-size: 15px;
  font-weight: 600;
  color: #111827;
}

.col-na {
  color: #D1D5DB;
}
</style>
