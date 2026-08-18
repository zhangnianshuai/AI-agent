<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { createJob } from '@/api/job'
import { listCompanies } from '@/api/company'
import { ElMessage } from 'element-plus'

const router = useRouter()

const formRef = ref(null)
const companies = ref([])

const form = reactive({
  company_id: '',
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

const rules = {
  company_id: [{ required: true, message: '请选择公司', trigger: 'change' }],
  title: [{ required: true, message: '请输入职位名称', trigger: 'blur' }],
}

const categories = ['技术', '产品', '设计', '运营', '市场', '销售', '财务', '人事', '行政']
const educations = ['不限', '高中', '大专', '本科', '硕士', '博士']
const experiences = ['不限', '应届生', '1-3年', '3-5年', '5-10年', '10年以上']

const loading = ref(false)
const companyLoading = ref(true)

async function fetchCompanies() {
  try {
    const data = await listCompanies()
    companies.value = data || []
  } catch {
    companies.value = []
  } finally {
    companyLoading.value = false
  }
}

async function handleSubmit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    const result = await createJob(form)
    ElMessage.success('职位创建成功')
    router.push(`/jobs/${result.job_id}`)
  } catch {
    // Error handled by interceptor
  } finally {
    loading.value = false
  }
}

fetchCompanies()
</script>

<template>
  <div class="job-create">
    <h1 class="page-title">发布职位</h1>

    <el-card>
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="120px"
        label-position="right"
      >
        <el-form-item label="所属公司" prop="company_id">
          <el-select
            v-model="form.company_id"
            placeholder="请选择公司"
            :loading="companyLoading"
            style="width: 100%"
          >
            <el-option
              v-for="c in companies"
              :key="c.id || c.company_id"
              :label="c.name"
              :value="c.id || c.company_id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="职位名称" prop="title">
          <el-input v-model="form.title" placeholder="如：高级前端工程师" />
        </el-form-item>

        <el-form-item label="工作地点">
          <el-input v-model="form.location" placeholder="如：北京" />
        </el-form-item>

        <el-form-item label="职位类别">
          <el-select v-model="form.category" placeholder="选择类别" style="width: 100%">
            <el-option v-for="c in categories" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>

        <el-form-item label="薪资范围">
          <el-row :gutter="16" style="width: 100%">
            <el-col :span="11">
              <el-input-number
                v-model="form.salary_min"
                :min="0"
                placeholder="最低 (K)"
                controls-position="right"
                style="width: 100%"
              />
            </el-col>
            <el-col :span="2" style="text-align: center; line-height: 32px">-</el-col>
            <el-col :span="11">
              <el-input-number
                v-model="form.salary_max"
                :min="0"
                placeholder="最高 (K)"
                controls-position="right"
                style="width: 100%"
              />
            </el-col>
          </el-row>
        </el-form-item>

        <el-form-item label="学历要求">
          <el-select v-model="form.education_requirement" placeholder="不限" style="width: 100%">
            <el-option v-for="e in educations" :key="e" :label="e" :value="e === '不限' ? '' : e" />
          </el-select>
        </el-form-item>

        <el-form-item label="经验要求">
          <el-select v-model="form.experience_requirement" placeholder="不限" style="width: 100%">
            <el-option v-for="e in experiences" :key="e" :label="e" :value="e === '不限' ? '' : e" />
          </el-select>
        </el-form-item>

        <el-form-item label="招聘人数">
          <el-input-number v-model="form.headcount" :min="1" :max="999" />
        </el-form-item>

        <el-form-item label="职位描述">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="8"
            placeholder="请输入详细的职位描述..."
          />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" size="large" :loading="loading" @click="handleSubmit">
            发布职位
          </el-button>
          <el-button size="large" @click="router.back()">取消</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.job-create {
  max-width: 800px;
}

.page-title {
  font-size: var(--font-size-2xl);
  margin: 0 0 var(--space-6);
  color: var(--color-text);
}
</style>
