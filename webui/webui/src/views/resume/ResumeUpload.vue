<script setup>
import { ref, reactive, computed, watch, nextTick, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { getToken, splitSkills } from '@/utils'
import {
  loadResume,
  uploadResume,
} from '@/api/resume'
import { ElMessage } from 'element-plus'
import { UploadFilled, Delete, Plus } from '@element-plus/icons-vue'
import { DotLottie } from '@lottiefiles/dotlottie-web'

const router = useRouter()

const canvasRef = ref(null)
let dotLottie = null

// ── state ───────────────────────────────────────────────────
const step = ref(1)                    // 1=上传解析  2=编辑保存
const fileList = ref([])
const fileName = ref('')
const fileUrl = ref('')
const uploading = ref(false)
const parsing = ref(false)
const saving = ref(false)
const saved = ref(false)

const editForm = reactive({
  name: '',
  age: null,
  sex: '',
  work_year: '',
  job_intention: '',
  skills: '',
  self_evaluation: '',
  education: [],
  projects: [],
})

const hasFile = computed(() => !!fileUrl.value)

// 解析开始时创建 DotLottie 实例，结束时销毁
watch(parsing, async (val) => {
  if (val) {
    await nextTick()
    const canvas = canvasRef.value
    if (canvas) {
      dotLottie = new DotLottie({
        autoplay: true,
        loop: true,
        canvas,
        src: '/pdf scanning.lottie',
      })
    }
  } else {
    dotLottie?.destroy()
    dotLottie = null
  }
})

onBeforeUnmount(() => {
  dotLottie?.destroy()
})

// ── upload ──────────────────────────────────────────────────
function handleUploadSuccess(response, file) {
  if (response.code === 200) {
    fileUrl.value = 'uploaded'
    fileName.value = file.name
    ElMessage.success('文件上传成功')
  }
}

function handleUploadError() {
  ElMessage.error('文件上传失败')
}

function handleRemove() {
  fileName.value = ''
  fileUrl.value = ''
}

// ── parse ───────────────────────────────────────────────────
async function handleParse() {
  if (!fileUrl.value) {
    ElMessage.warning('请先上传简历文件')
    return
  }
  parsing.value = true
  try {
    const data = await loadResume()
    editForm.name = data.name || ''
    editForm.age = data.age ?? null
    editForm.sex = data.sex || ''
    editForm.work_year = data.work_year || ''
    editForm.job_intention = data.job_intention || ''
    editForm.skills = Array.isArray(data.skills) ? data.skills.join('，') : (data.skills || '')
    editForm.self_evaluation = data.self_evaluation || ''
    editForm.education = data.education || []
    editForm.projects = data.projects || []

    step.value = 2
  } catch (err) {
    ElMessage.error(err?.response?.data?.message || err?.message || '简历解析失败，请检查文件是否为有效PDF')
  } finally {
    parsing.value = false
  }
}

// ── save ────────────────────────────────────────────────────
async function handleSave() {
  saving.value = true
  try {
    await uploadResume({
      file_name: fileName.value,
      file_url: fileUrl.value,
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
    saved.value = true
    ElMessage.success('简历保存成功')
    router.push('/resume/view')
  } catch {
    // Handled by interceptor
  } finally {
    saving.value = false
  }
}

function getSkills(skills) {
  return splitSkills(skills)
}
</script>

<template>
  <div class="resume-upload">

    <!-- ══════════════════════════════════════════════════════ -->
    <!-- Step 1: Upload + Parse -->
    <!-- ══════════════════════════════════════════════════════ -->
    <template v-if="step === 1">
      <h1 class="page-title">上传简历</h1>

      <!-- Upload card -->
      <el-card class="step-card">
        <!-- No file: show upload area -->
        <div v-if="!hasFile && !parsing">
          <el-upload
            v-model:file-list="fileList"
            :action="`/api/file/upload`"
            :data="{ category: 'resume' }"
            :headers="{ Authorization: `Bearer ${getToken() || ''}` }"
            :limit="1"
            accept=".pdf"
            :on-success="handleUploadSuccess"
            :on-error="handleUploadError"
            :on-remove="handleRemove"
            :show-file-list="false"
            drag
          >
            <el-icon :size="48"><UploadFilled /></el-icon>
            <div class="upload-text">点击或拖拽上传 PDF 简历</div>
          </el-upload>
        </div>

        <!-- File uploaded: show info + actions -->
        <div v-if="hasFile && !parsing" class="file-info">
          <div class="file-card">
            <span class="file-icon">📄</span>
            <span class="file-name">{{ fileName }}</span>
            <el-button type="primary" link @click="fileUrl = ''; fileName = ''; fileList = []">重新上传</el-button>
          </div>

          <el-button
            type="primary"
            size="large"
            class="parse-btn"
            @click="handleParse"
          >
            简历解析
          </el-button>
        </div>

        <!-- Parsing animation -->
        <div v-if="parsing" class="parse-animation">
          <canvas ref="canvasRef" width="260" height="260"></canvas>
          <p class="parse-text">AI 正在解析简历，请稍候...</p>
        </div>
      </el-card>
    </template>

    <!-- ══════════════════════════════════════════════════════ -->
    <!-- Step 2: Edit + Save -->
    <!-- ══════════════════════════════════════════════════════ -->
    <template v-if="step === 2">
      <div class="page-header">
        <h1 class="page-title">核对并修改简历信息</h1>
        <div class="header-actions">
          <el-button type="primary" :loading="saving" :disabled="saved" @click="handleSave">
            {{ saved ? '已保存' : '保存简历' }}
          </el-button>
        </div>
      </div>

      <!-- 基本信息 -->
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

      <!-- 教育经历 -->
      <el-card class="section-card">
        <template #header>
          <div class="section-header">
            <h3>教育经历</h3>
            <el-button size="small" :icon="Plus" class="add-btn" @click="editForm.education.push({school_name:'',degree:'',major:'',start_date:'',end_date:''})">添加</el-button>
          </div>
        </template>
        <div v-if="!editForm.education.length" class="empty-placeholder">
          <span class="text-muted">暂无教育经历</span>
          <el-button type="primary" plain :icon="Plus" @click="editForm.education.push({school_name:'',degree:'',major:'',start_date:'',end_date:''})">添加</el-button>
        </div>
        <div v-for="(edu, i) in editForm.education" :key="i" class="edit-block">
          <el-button type="danger" size="small" circle class="block-delete" @click="editForm.education.splice(i, 1)"><el-icon><Delete /></el-icon></el-button>
          <el-row :gutter="12">
            <el-col :span="8"><el-form-item label="学校"><el-input v-model="edu.school_name" /></el-form-item></el-col>
            <el-col :span="5"><el-form-item label="学位"><el-input v-model="edu.degree" /></el-form-item></el-col>
            <el-col :span="5"><el-form-item label="专业"><el-input v-model="edu.major" /></el-form-item></el-col>
            <el-col :span="3"><el-form-item label="开始"><el-input v-model="edu.start_date" /></el-form-item></el-col>
            <el-col :span="3"><el-form-item label="结束"><el-input v-model="edu.end_date" /></el-form-item></el-col>
          </el-row>
        </div>
      </el-card>

      <!-- 项目经历 -->
      <el-card class="section-card">
        <template #header>
          <div class="section-header">
            <h3>项目经历</h3>
            <el-button size="small" :icon="Plus" class="add-btn" @click="editForm.projects.push({project_name:'',role:'',description:'',start_date:'',end_date:''})">添加</el-button>
          </div>
        </template>
        <div v-if="!editForm.projects.length" class="empty-placeholder">
          <span class="text-muted">暂无项目经历</span>
          <el-button type="primary" plain :icon="Plus" @click="editForm.projects.push({project_name:'',role:'',description:'',start_date:'',end_date:''})">添加</el-button>
        </div>
        <div v-for="(p, i) in editForm.projects" :key="i" class="edit-block">
          <el-button type="danger" size="small" circle class="block-delete" @click="editForm.projects.splice(i, 1)"><el-icon><Delete /></el-icon></el-button>
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

  </div>
</template>

<style scoped>
.resume-upload {
  max-width: 1100px;
}

/* ── Page header (shared by both steps) ──────────────── */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-6);
}

.page-title {
  font-size: var(--font-size-2xl);
  color: var(--color-text);
  margin: 0 0 var(--space-6);
}

.page-header .page-title {
  margin-bottom: 0;
}

.header-actions {
  display: flex;
  gap: var(--space-3);
}

/* ── Card base ───────────────────────────────────────── */
.step-card,
.section-card {
  margin-bottom: var(--space-4);
}

.section-card h3 { margin: 0; }

/* ── Step 1: Upload ──────────────────────────────────── */
.upload-text {
  color: var(--color-text-muted);
  margin-top: var(--space-2);
}

.file-info {
  margin-top: var(--space-5);
  text-align: center;
}

.file-card {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-5);
  background: var(--color-bg-alt);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.file-icon { font-size: 24px; }

.file-name {
  font-size: var(--font-size-base);
  color: var(--color-text);
  max-width: 400px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.parse-btn {
  display: block;
  margin: var(--space-6) auto 0;
  min-width: 160px;
}

.parse-animation {
  text-align: center;
  padding: var(--space-6) 0;
}

.parse-text {
  color: var(--color-text-secondary);
  font-size: var(--font-size-base);
  margin-top: var(--space-4);
}

/* ── Step 2: Edit (same as ResumeView) ───────────────── */
.section-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.section-header h3 { margin: 0; }

.edit-block {
  padding: var(--space-3);
  padding-top: var(--space-6);
  padding-right: 36px;       /* 给右上角删除按钮留空间 */
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

.add-btn {
  border: 1px dashed var(--el-color-primary) !important;
  color: var(--el-color-primary) !important;
  background: transparent !important;
}

.add-btn:hover {
  border-style: solid !important;
  background: var(--el-color-primary-light-9) !important;
}

.empty-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-6) 0;
}
</style>
