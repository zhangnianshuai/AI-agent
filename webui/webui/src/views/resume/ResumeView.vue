<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { getResume, uploadResume } from '@/api/resume'
import { splitSkills } from '@/utils'
import { ElMessage } from 'element-plus'
import { Edit } from '@element-plus/icons-vue'

const router = useRouter()
const resume = ref(null)
const loading = ref(true)
const editing = ref(false)
const saving = ref(false)
const dirty = ref(false)

const editForm = reactive({
  name: '', age: null, sex: '', work_year: '',
  job_intention: '', skills: '', self_evaluation: '',
  education: [], projects: [],
})

// Watch for changes to mark dirty
watch(() => ({ ...editForm }), () => { if (editing.value) dirty.value = true }, { deep: true })

function getSkills(skills) {
  return splitSkills(skills)
}

function startEdit() {
  if (!resume.value) return
  editForm.name = resume.value.name || ''
  editForm.age = resume.value.age || null
  editForm.sex = resume.value.sex || ''
  editForm.work_year = resume.value.work_year || ''
  editForm.job_intention = resume.value.job_intention || ''
  editForm.skills = Array.isArray(resume.value.skills) ? resume.value.skills.join('，') : (resume.value.skills || '')
  editForm.self_evaluation = resume.value.self_evaluation || ''
  editForm.education = JSON.parse(JSON.stringify(resume.value.education || []))
  editForm.projects = JSON.parse(JSON.stringify(resume.value.projects || []))
  dirty.value = false
  editing.value = true
}

function cancelEdit() {
  editing.value = false
  dirty.value = false
}

async function handleSave() {
  if (!dirty.value) return
  saving.value = true
  try {
    await uploadResume({
      file_name: resume.value?.file_name || '',
      file_url: resume.value?.file_url || '',
      name: editForm.name,
      age: editForm.age,
      sex: editForm.sex,
      work_year: editForm.work_year,
      skills: editForm.skills,
      self_evaluation: editForm.self_evaluation,
      job_intention: editForm.job_intention,
      education: editForm.education,
      projects: editForm.projects,
    })
    ElMessage.success('简历已更新')
    editing.value = false
    dirty.value = false
    // Refresh
    resume.value = await getResume()
  } catch {
    // Handled by interceptor
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  try {
    resume.value = await getResume()
  } catch { /* handled */ }
  finally { loading.value = false }
})
</script>

<template>
  <div class="resume-view" v-loading="loading">
    <div class="page-header">
      <h1 class="page-title">我的简历</h1>
      <div class="header-actions">
        <template v-if="!editing">
          <el-button type="primary" :icon="Edit" @click="startEdit" v-if="resume">编辑简历</el-button>
        </template>
        <template v-else>
          <el-button @click="cancelEdit">取消</el-button>
          <el-button type="primary" :loading="saving" :disabled="!dirty" @click="handleSave">保存修改</el-button>
        </template>
      </div>
    </div>

    <!-- View Mode -->
    <template v-if="resume && !editing">
      <el-card class="section-card">
        <template #header><h3>基本信息</h3></template>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="姓名">{{ resume.name }}</el-descriptions-item>
          <el-descriptions-item label="年龄">{{ resume.age }}</el-descriptions-item>
          <el-descriptions-item label="性别">{{ resume.sex }}</el-descriptions-item>
          <el-descriptions-item label="工作年限">{{ resume.work_year }}</el-descriptions-item>
          <el-descriptions-item label="求职意向" :span="2">{{ resume.job_intention }}</el-descriptions-item>
          <el-descriptions-item label="技能" :span="2">
            <el-tag v-for="s in getSkills(resume.skills)" :key="s" size="small" style="margin: 2px">{{ s }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="自我评价" :span="2">{{ resume.self_evaluation }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card class="section-card" v-if="resume.education && resume.education.length">
        <template #header><h3>教育经历</h3></template>
        <el-table :data="resume.education" stripe>
          <el-table-column prop="school_name" label="学校" />
          <el-table-column prop="degree" label="学位" />
          <el-table-column prop="major" label="专业" />
          <el-table-column prop="start_date" label="开始时间" />
          <el-table-column prop="end_date" label="结束时间" />
        </el-table>
      </el-card>

      <el-card class="section-card" v-if="resume.projects && resume.projects.length">
        <template #header><h3>项目经历</h3></template>
        <div v-for="(p, i) in resume.projects" :key="i" class="project-item">
          <h4>{{ p.project_name }} <el-tag size="small">{{ p.role }}</el-tag></h4>
          <p class="project-desc">{{ p.description }}</p>
          <p class="project-date" v-if="p.start_date || p.end_date">{{ p.start_date }} ~ {{ p.end_date }}</p>
        </div>
      </el-card>
    </template>

    <!-- Edit Mode -->
    <template v-else-if="editing">
      <el-card class="section-card">
        <template #header><h3>基本信息</h3></template>
        <el-form :model="editForm" label-width="100px" label-position="right">
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="姓名"><el-input v-model="editForm.name" /></el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="年龄"><el-input-number v-model="editForm.age" :min="0" :max="100" /></el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="性别">
                <el-select v-model="editForm.sex" style="width: 100%">
                  <el-option label="男" value="男" /><el-option label="女" value="女" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="工作年限"><el-input v-model="editForm.work_year" /></el-form-item>
            </el-col>
          </el-row>
          <el-form-item label="求职意向"><el-input v-model="editForm.job_intention" /></el-form-item>
          <el-form-item label="技能">
            <el-input v-model="editForm.skills" placeholder="逗号分隔" />
            <div style="margin-top: 6px">
              <el-tag v-for="s in getSkills(editForm.skills)" :key="s" size="small" style="margin: 2px">{{ s }}</el-tag>
            </div>
          </el-form-item>
          <el-form-item label="自我评价">
            <el-input v-model="editForm.self_evaluation" type="textarea" :rows="3" />
          </el-form-item>
        </el-form>
      </el-card>

      <!-- Education -->
      <el-card class="section-card">
        <template #header>
          <div class="section-header">
            <h3>教育经历</h3>
            <el-button size="small" type="primary" link @click="editForm.education.push({school_name:'',degree:'',major:'',start_date:'',end_date:''})">+ 添加</el-button>
          </div>
        </template>
        <div v-if="!editForm.education.length" class="text-muted">暂无，点击上方添加</div>
        <div v-for="(edu, i) in editForm.education" :key="i" class="edit-block">
          <el-button type="danger" size="small" circle class="block-delete" @click="editForm.education.splice(i, 1)">✕</el-button>
          <el-row :gutter="12">
            <el-col :span="8"><el-form-item label="学校"><el-input v-model="edu.school_name" /></el-form-item></el-col>
            <el-col :span="5"><el-form-item label="学位"><el-input v-model="edu.degree" /></el-form-item></el-col>
            <el-col :span="5"><el-form-item label="专业"><el-input v-model="edu.major" /></el-form-item></el-col>
            <el-col :span="3"><el-form-item label="开始"><el-input v-model="edu.start_date" /></el-form-item></el-col>
            <el-col :span="3"><el-form-item label="结束"><el-input v-model="edu.end_date" /></el-form-item></el-col>
          </el-row>
        </div>
      </el-card>

      <!-- Projects -->
      <el-card class="section-card">
        <template #header>
          <div class="section-header">
            <h3>项目经历</h3>
            <el-button size="small" type="primary" link @click="editForm.projects.push({project_name:'',role:'',description:'',start_date:'',end_date:''})">+ 添加</el-button>
          </div>
        </template>
        <div v-if="!editForm.projects.length" class="text-muted">暂无，点击上方添加</div>
        <div v-for="(p, i) in editForm.projects" :key="i" class="edit-block">
          <el-button type="danger" size="small" circle class="block-delete" @click="editForm.projects.splice(i, 1)">✕</el-button>
          <el-row :gutter="12">
            <el-col :span="8"><el-form-item label="项目名"><el-input v-model="p.project_name" /></el-form-item></el-col>
            <el-col :span="4"><el-form-item label="角色"><el-input v-model="p.role" /></el-form-item></el-col>
            <el-col :span="6"><el-form-item label="开始"><el-input v-model="p.start_date" /></el-form-item></el-col>
            <el-col :span="6"><el-form-item label="结束"><el-input v-model="p.end_date" /></el-form-item></el-col>
          </el-row>
          <el-form-item label="描述"><el-input v-model="p.description" type="textarea" :rows="4" /></el-form-item>
        </div>
      </el-card>
    </template>

    <el-empty v-else-if="!loading" description="暂无简历数据">
      <el-button type="primary" @click="router.push('/resume')">去上传简历</el-button>
    </el-empty>
  </div>
</template>

<style scoped>
.resume-view {
  max-width: 1100px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-6);
}

.page-title {
  font-size: var(--font-size-2xl);
  color: var(--color-text);
  margin: 0;
}

.header-actions {
  display: flex;
  gap: var(--space-3);
}

.section-card {
  margin-bottom: var(--space-4);
}

.section-card h3 { margin: 0; }

.section-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.section-header h3 { margin: 0; }

.project-item {
  padding: var(--space-4);
  background: var(--color-bg-alt);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-3);
}

.project-item h4 {
  margin: 0 0 var(--space-2);
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.project-desc { color: var(--color-text-secondary); margin: 4px 0; }
.project-date { color: var(--color-text-muted); font-size: var(--font-size-xs); }

.edit-block {
  padding: var(--space-3);
  padding-top: var(--space-6);
  margin-bottom: var(--space-3);
  background: var(--color-bg-alt);
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
  position: relative;
}

.block-delete {
  position: absolute;
  top: 6px;
  right: 6px;
  z-index: 1;
}

.text-muted {
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
}
</style>
