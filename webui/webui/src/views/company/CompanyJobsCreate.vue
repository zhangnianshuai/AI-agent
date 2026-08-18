<script setup>
import { ref, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { createJob } from '@/api/job'
import { ElMessage } from 'element-plus'

const route = useRoute()
const router = useRouter()
const companyId = route.params.id

const saving = ref(false)
const form = reactive({
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

async function handleSubmit() {
  if (!form.title) { ElMessage.warning('请输入岗位名称'); return }
  saving.value = true
  try {
    await createJob({ ...form, company_id: companyId })
    ElMessage.success('岗位创建成功')
    router.push(`/companies/${companyId}/jobs`)
  } catch { /* handled */ }
  finally { saving.value = false }
}
</script>

<template>
  <div class="job-create">
    <div class="page-header">
      <h2 class="page-title">创建岗位</h2>
    </div>

    <el-card>
      <el-form :model="form" label-width="100px" label-position="top">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="岗位名称" required>
              <el-input v-model="form.title" placeholder="如：前端开发工程师" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="工作地点">
              <el-input v-model="form.location" placeholder="如：北京" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="职位类别">
              <el-select v-model="form.category" style="width: 100%" placeholder="选择类别">
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
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="最低薪资（元）">
              <el-input-number v-model="form.salary_min" :min="0" :step="1000" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="最高薪资（元）">
              <el-input-number v-model="form.salary_max" :min="0" :step="1000" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
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
          <el-input v-model="form.description" type="textarea" :rows="5" placeholder="请描述该岗位的工作内容与要求" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="saving" @click="handleSubmit">创建岗位</el-button>
          <el-button @click="router.push(`/companies/${companyId}/jobs`)">取消</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.job-create { max-width: 800px; }

.page-header {
  margin-bottom: var(--space-4);
}

.page-title {
  font-size: var(--font-size-xl);
  color: var(--color-text);
  margin: 0;
}
</style>
