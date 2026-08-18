<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { createCompany } from '@/api/company'
import { ElMessage } from 'element-plus'

const router = useRouter()

const formRef = ref(null)
const form = reactive({
  name: '',
  short_name: '',
  industry: '',
  scale: '',
  description: '',
  address: '',
  website: '',
  logo_url: '',
  contact_person: '',
  contact_phone: '',
})

const rules = {
  name: [{ required: true, message: '请输入公司名称', trigger: 'blur' }],
}

const industries = ['互联网', '金融', '教育', '医疗', '制造', '零售', '房地产', '物流', '能源', '其他']
const scales = ['少于50人', '50-150人', '150-500人', '500-2000人', '2000人以上']

const loading = ref(false)

async function handleSubmit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    const result = await createCompany(form)
    ElMessage.success(`公司 "${result.name}" 创建成功`)
    router.push('/companies')
  } catch {
    // Handled by interceptor
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="company-create">
    <h1 class="page-title">创建公司</h1>

    <el-card>
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="120px"
        label-position="right"
      >
        <el-form-item label="公司名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入公司全称" />
        </el-form-item>

        <el-form-item label="简称">
          <el-input v-model="form.short_name" placeholder="公司简称" />
        </el-form-item>

        <el-form-item label="行业">
          <el-select v-model="form.industry" placeholder="选择行业" style="width: 100%">
            <el-option v-for="ind in industries" :key="ind" :label="ind" :value="ind" />
          </el-select>
        </el-form-item>

        <el-form-item label="规模">
          <el-select v-model="form.scale" placeholder="选择规模" style="width: 100%">
            <el-option v-for="s in scales" :key="s" :label="s" :value="s" />
          </el-select>
        </el-form-item>

        <el-form-item label="公司地址">
          <el-input v-model="form.address" placeholder="公司地址" />
        </el-form-item>

        <el-form-item label="官网">
          <el-input v-model="form.website" placeholder="https://..." />
        </el-form-item>

        <el-form-item label="Logo URL">
          <el-input v-model="form.logo_url" placeholder="Logo 图片链接" />
        </el-form-item>

        <el-form-item label="联系人">
          <el-input v-model="form.contact_person" placeholder="联系人姓名" />
        </el-form-item>

        <el-form-item label="联系电话">
          <el-input v-model="form.contact_phone" placeholder="联系电话" />
        </el-form-item>

        <el-form-item label="公司描述">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="4"
            placeholder="请输入公司简介..."
          />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" size="large" :loading="loading" @click="handleSubmit">
            创建公司
          </el-button>
          <el-button size="large" @click="router.back()">取消</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.company-create {
  max-width: 700px;
}

.page-title {
  font-size: var(--font-size-2xl);
  margin: 0 0 var(--space-6);
  color: var(--color-text);
}
</style>
