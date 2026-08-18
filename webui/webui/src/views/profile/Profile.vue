<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { getResume, uploadResume } from '@/api/resume'
import { splitSkills } from '@/utils'
import { ElMessage } from 'element-plus'
import { UserFilled, Lock, Edit, Plus, Delete, Document, Collection, Upload } from '@element-plus/icons-vue'
import { uploadAvatar } from '@/api/user'
import defaultAvatar from '@/assets/user/vue-color-avatar.png'

const router = useRouter()
const auth = useAuthStore()

const avatarPreview = computed(() => profileForm.avatar_url || defaultAvatar)

// ═══ Profile ═══
const profileFormRef = ref(null)
const passwordFormRef = ref(null)
const profileLoading = ref(false)
const passwordLoading = ref(false)
const passwordDialogVisible = ref(false)
const editingProfile = ref(false)

const profileForm = reactive({ email: '', phone: '', real_name: '', avatar_url: '' })

const passwordForm = reactive({ old_password: '', new_password: '', confirm_password: '' })

const pwRules = {
  old_password: [{ required: true, message: '请输入旧密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, max: 20, message: '6-20个字符', trigger: 'blur' },
  ],
  confirm_password: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    { validator: (_r, v, cb) => cb(v !== passwordForm.new_password ? new Error('两次密码输入不一致') : undefined), trigger: 'blur' },
  ],
}

onMounted(() => {
  if (auth.user) {
    profileForm.email = auth.user.email || ''
    profileForm.phone = auth.user.phone || ''
    profileForm.real_name = auth.user.real_name || ''
    profileForm.avatar_url = auth.user.avatar_url || ''
  }
  fetchResume()
})

const avatarUploading = ref(false)
async function handleAvatarUpload(file) {
  avatarUploading.value = true
  try {
    const res = await uploadAvatar(file)
    profileForm.avatar_url = res.url || profileForm.avatar_url
    ElMessage.success('头像上传成功')
  } catch { /* handled */ }
  finally { avatarUploading.value = false }
}

function startEditProfile() {
  if (auth.user) {
    profileForm.email = auth.user.email || ''
    profileForm.phone = auth.user.phone || ''
    profileForm.real_name = auth.user.real_name || ''
    profileForm.avatar_url = auth.user.avatar_url || ''
  }
  editingProfile.value = true
}

function cancelEditProfile() {
  editingProfile.value = false
}

async function handleUpdateProfile() {
  try { await profileFormRef.value.validate() } catch { return }
  profileLoading.value = true
  try {
    await auth.updateProfile(profileForm)
    ElMessage.success('个人资料已更新')
    editingProfile.value = false
  } finally { profileLoading.value = false }
}

function openPasswordDialog() {
  passwordForm.old_password = ''
  passwordForm.new_password = ''
  passwordForm.confirm_password = ''
  passwordDialogVisible.value = true
}

async function handleUpdatePassword() {
  try { await passwordFormRef.value.validate() } catch { return }
  passwordLoading.value = true
  try {
    await auth.updatePassword({ old_password: passwordForm.old_password, new_password: passwordForm.new_password })
    ElMessage.success('密码已修改')
    passwordDialogVisible.value = false
  } finally { passwordLoading.value = false }
}

// ═══ Resume ═══
const resume = ref(null)
const resumeLoading = ref(true)
const editing = ref(false)
const saving = ref(false)
const dirty = ref(false)

const editForm = reactive({
  name: '', age: null, sex: '', work_year: '',
  job_intention: '', skills: '', self_evaluation: '',
  education: [], projects: [],
})

watch(() => ({ ...editForm }), () => { if (editing.value) dirty.value = true }, { deep: true })

function getSkills(skills) {
  return splitSkills(skills)
}

async function fetchResume() {
  resumeLoading.value = true
  try { resume.value = await getResume() } catch { resume.value = null }
  finally { resumeLoading.value = false }
}

function startEdit() {
  const r = resume.value || {}
  editForm.name = r.name || profileForm.real_name || ''
  editForm.age = r.age || null
  editForm.sex = r.sex || ''
  editForm.work_year = r.work_year || ''
  editForm.job_intention = r.job_intention || ''
  editForm.skills = Array.isArray(r.skills) ? r.skills.join('，') : (r.skills || '')
  editForm.self_evaluation = r.self_evaluation || ''
  editForm.education = JSON.parse(JSON.stringify(r.education || []))
  editForm.projects = JSON.parse(JSON.stringify(r.projects || []))
  dirty.value = false
  editing.value = true
}

function cancelEdit() {
  editing.value = false
  dirty.value = false
}

async function handleSaveResume() {
  if (!dirty.value) { editing.value = false; return }
  saving.value = true
  try {
    await uploadResume({
      file_name: resume.value?.file_name || '',
      file_url: resume.value?.file_url || '',
      name: editForm.name, age: editForm.age, sex: editForm.sex,
      work_year: editForm.work_year, skills: editForm.skills,
      self_evaluation: editForm.self_evaluation, job_intention: editForm.job_intention,
      education: editForm.education, projects: editForm.projects,
    })
    ElMessage.success('简历已更新')
    editing.value = false
    resume.value = await getResume()
  } catch { /* handled */ }
  finally { saving.value = false }
}
</script>

<template>
  <div class="profile-page">
    <h1 class="page-title">个人中心</h1>

    <!-- ═══ Profile Card ═══ -->
    <el-card class="section-card">
      <template #header>
        <div class="card-header">
          <div class="card-header-left">
            <el-icon><UserFilled /></el-icon>
            <span>基本信息</span>
          </div>
          <div class="card-header-right">
            <template v-if="!editingProfile">
              <el-button size="small" :icon="Edit" @click="startEditProfile">修改</el-button>
            </template>
            <template v-else>
              <el-button size="small" @click="cancelEditProfile">取消</el-button>
              <el-button size="small" type="primary" :loading="profileLoading" @click="handleUpdateProfile">保存</el-button>
            </template>
            <el-button size="small" :icon="Lock" @click="openPasswordDialog">修改密码</el-button>
          </div>
        </div>
      </template>

      <div class="avatar-section">
        <el-avatar :size="72" :src="avatarPreview" class="profile-avatar" @error="() => {}">
          {{ (auth.user?.real_name || auth.user?.username || 'U').charAt(0).toUpperCase() }}
        </el-avatar>
        <div class="avatar-info">
          <span class="avatar-name">{{ auth.user?.real_name || auth.user?.username }}</span>
          <el-tag :type="auth.isAdmin ? 'danger' : auth.isHR ? 'warning' : 'info'" size="small">
            {{ auth.isAdmin ? '管理员' : auth.isHR ? 'HR' : '候选人' }}
          </el-tag>
        </div>
      </div>

      <el-form ref="profileFormRef" :model="profileForm" label-width="80px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="真实姓名">
              <el-input v-model="profileForm.real_name" :disabled="!editingProfile" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="邮箱">
              <el-input v-model="profileForm.email" :disabled="!editingProfile" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="手机号">
              <el-input v-model="profileForm.phone" :disabled="!editingProfile" />
            </el-form-item>
          </el-col>
          <el-col :span="12" v-if="editingProfile">
            <el-form-item label="头像">
              <div class="avatar-edit-row">
                <el-input v-model="profileForm.avatar_url" placeholder="输入图片URL 或 上传文件" style="flex:1" />
                <el-upload
                  :show-file-list="false"
                  :before-upload="(f) => { handleAvatarUpload(f); return false }"
                  accept="image/*"
                >
                  <el-button :icon="Upload" :loading="avatarUploading">上传</el-button>
                </el-upload>
              </div>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </el-card>

    <!-- ═══ Resume Data ═══ -->
    <el-card class="section-card" v-loading="resumeLoading">
      <template #header>
        <div class="card-header">
          <span>我的简历</span>
          <div class="card-header-right">
            <template v-if="!editing && resume">
              <el-button size="small" :icon="Edit" @click="startEdit">编辑</el-button>
            </template>
            <template v-if="!editing && !resume && !resumeLoading">
              <el-button size="small" :icon="Plus" type="primary" @click="startEdit">直接编辑</el-button>
            </template>
            <template v-if="editing">
              <el-button size="small" @click="cancelEdit">取消</el-button>
              <el-button size="small" type="primary" :loading="saving" :disabled="!dirty" @click="handleSaveResume">保存</el-button>
            </template>
          </div>
        </div>
      </template>

      <!-- View Mode -->
      <template v-if="resume && !editing">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="姓名">{{ resume.name }}</el-descriptions-item>
          <el-descriptions-item label="年龄">{{ resume.age }}</el-descriptions-item>
          <el-descriptions-item label="性别">{{ resume.sex }}</el-descriptions-item>
          <el-descriptions-item label="工作年限">{{ resume.work_year }}</el-descriptions-item>
          <el-descriptions-item label="求职意向" :span="2">{{ resume.job_intention }}</el-descriptions-item>
          <el-descriptions-item label="技能" :span="2">
            <el-tag v-for="s in getSkills(resume.skills)" :key="s" size="small" class="skill-tag">{{ s }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="自我评价" :span="2">{{ resume.self_evaluation }}</el-descriptions-item>
        </el-descriptions>

        <div v-if="resume.education?.length" style="margin-top: 20px">
          <h4 class="sub-title">教育经历</h4>
          <el-table :data="resume.education" stripe size="small">
            <el-table-column prop="school_name" label="学校" />
            <el-table-column prop="degree" label="学位" />
            <el-table-column prop="major" label="专业" />
            <el-table-column prop="start_date" label="开始" />
            <el-table-column prop="end_date" label="结束" />
          </el-table>
        </div>

        <div v-if="resume.projects?.length" style="margin-top: 20px">
          <h4 class="sub-title">项目经历</h4>
          <div v-for="(p, i) in resume.projects" :key="i" class="project-item">
            <h5>{{ p.project_name }} <el-tag size="small">{{ p.role }}</el-tag></h5>
            <p class="project-desc">{{ p.description }}</p>
            <p class="project-date" v-if="p.start_date || p.end_date">{{ p.start_date }} ~ {{ p.end_date }}</p>
          </div>
        </div>
      </template>

      <!-- Edit Mode -->
      <template v-if="editing">
        <el-form :model="editForm" label-width="90px">
          <el-row :gutter="16">
            <el-col :span="12"><el-form-item label="姓名"><el-input v-model="editForm.name" /></el-form-item></el-col>
            <el-col :span="12"><el-form-item label="年龄"><el-input-number v-model="editForm.age" :min="0" :max="100" /></el-form-item></el-col>
          </el-row>
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="性别">
                <el-select v-model="editForm.sex" style="width:100%"><el-option label="男" value="男" /><el-option label="女" value="女" /></el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12"><el-form-item label="工作年限"><el-input v-model="editForm.work_year" /></el-form-item></el-col>
          </el-row>
          <el-form-item label="求职意向"><el-input v-model="editForm.job_intention" /></el-form-item>
          <el-form-item label="技能">
            <el-input v-model="editForm.skills" placeholder="逗号分隔" />
            <el-tag v-for="s in getSkills(editForm.skills)" :key="s" size="small" class="skill-tag">{{ s }}</el-tag>
          </el-form-item>
          <el-form-item label="自我评价"><el-input v-model="editForm.self_evaluation" type="textarea" :rows="3" /></el-form-item>
        </el-form>

        <div style="margin-top: 20px">
          <div class="sub-header">
            <h4 class="sub-title">教育经历</h4>
            <el-button size="small" type="primary" link @click="editForm.education.push({school_name:'',degree:'',major:'',start_date:'',end_date:''})">+ 添加</el-button>
          </div>
          <div v-for="(edu, i) in editForm.education" :key="i" class="edit-block">
            <el-button type="danger" :icon="Delete" size="small" circle plain class="block-del" @click="editForm.education.splice(i,1)" />
            <el-row :gutter="12">
              <el-col :span="7"><el-form-item label="学校"><el-input v-model="edu.school_name" /></el-form-item></el-col>
              <el-col :span="5"><el-form-item label="学位"><el-input v-model="edu.degree" /></el-form-item></el-col>
              <el-col :span="5"><el-form-item label="专业"><el-input v-model="edu.major" /></el-form-item></el-col>
              <el-col :span="3"><el-form-item label="开始"><el-input v-model="edu.start_date" /></el-form-item></el-col>
              <el-col :span="3"><el-form-item label="结束"><el-input v-model="edu.end_date" /></el-form-item></el-col>
            </el-row>
          </div>
        </div>

        <div style="margin-top: 20px">
          <div class="sub-header">
            <h4 class="sub-title">项目经历</h4>
            <el-button size="small" type="primary" link @click="editForm.projects.push({project_name:'',role:'',description:'',start_date:'',end_date:''})">+ 添加</el-button>
          </div>
          <div v-for="(p, i) in editForm.projects" :key="i" class="edit-block">
            <el-button type="danger" :icon="Delete" size="small" circle plain class="block-del" @click="editForm.projects.splice(i,1)" />
            <el-row :gutter="12">
              <el-col :span="8"><el-form-item label="项目名"><el-input v-model="p.project_name" /></el-form-item></el-col>
              <el-col :span="4"><el-form-item label="角色"><el-input v-model="p.role" /></el-form-item></el-col>
              <el-col :span="6"><el-form-item label="开始"><el-input v-model="p.start_date" /></el-form-item></el-col>
              <el-col :span="6"><el-form-item label="结束"><el-input v-model="p.end_date" /></el-form-item></el-col>
            </el-row>
            <el-row :gutter="12">
              <el-col :span="24"><el-form-item label="描述"><el-input v-model="p.description" type="textarea" :rows="3" /></el-form-item></el-col>
            </el-row>
          </div>
        </div>
      </template>

      <div v-if="!resume && !editing && !resumeLoading" class="empty-resume">
        <p>暂无简历数据，上传 PDF 智能解析或直接编辑</p>
      </div>
    </el-card>

    <!-- Password Dialog -->
    <el-dialog v-model="passwordDialogVisible" title="修改密码" width="400px">
      <el-form ref="passwordFormRef" :model="passwordForm" :rules="pwRules" label-width="90px">
        <el-form-item label="旧密码" prop="old_password">
          <el-input v-model="passwordForm.old_password" type="password" show-password />
        </el-form-item>
        <el-form-item label="新密码" prop="new_password">
          <el-input v-model="passwordForm.new_password" type="password" show-password />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirm_password">
          <el-input v-model="passwordForm.confirm_password" type="password" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="passwordDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="passwordLoading" @click="handleUpdatePassword">确认修改</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.profile-page { max-width: 900px; }

.page-title { font-size: var(--font-size-2xl); margin: 0 0 var(--space-6); color: var(--color-text); }

.section-card { margin-bottom: var(--space-5); }

.card-header { display: flex; justify-content: space-between; align-items: center; }
.card-header-left { display: flex; align-items: center; gap: var(--space-2); font-weight: 600; }
.card-header-right { display: flex; gap: var(--space-2); }

/* Avatar */
.avatar-section {
  display: flex; align-items: center; gap: var(--space-4);
  margin-bottom: var(--space-5); padding: var(--space-4);
  background: var(--color-bg-alt); border-radius: var(--radius-lg);
}
.profile-avatar { border: 3px solid var(--color-border); flex-shrink: 0; }
.avatar-info { display: flex; flex-direction: column; gap: 4px; }
.avatar-name { font-weight: 600; }

/* Resume */
.sub-title { margin: 0 0 var(--space-3); font-size: 15px; }
.sub-header { display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--space-3); }
.sub-header .sub-title { margin: 0; }
.skill-tag { margin: 2px; }

.project-item {
  padding: var(--space-3); background: var(--color-bg-alt);
  border-radius: var(--radius-md); margin-bottom: var(--space-3);
}
.project-item h5 { margin: 0 0 4px; display: flex; align-items: center; gap: var(--space-2); }
.project-desc { color: var(--color-text-secondary); margin: 4px 0; font-size: var(--font-size-sm); }
.project-date { color: var(--color-text-muted); font-size: var(--font-size-xs); }

.edit-block {
  padding: var(--space-4) var(--space-10) var(--space-4) var(--space-5);
  background: var(--color-surface); border-radius: var(--radius-md);
  border: 1px solid var(--color-border); border-left: 3px solid var(--color-primary);
  position: relative; margin-bottom: var(--space-3);
}
.edit-block:hover { border-color: var(--color-primary-border); }
.block-del { position: absolute; top: 8px; right: 8px; z-index: 1; }

/* 项目行右侧留白，避免被删除按钮遮挡 */
.edit-block :deep(.el-row) {
  padding-right: var(--space-10);
}

.empty-resume {
  text-align: center; padding: var(--space-8);
  color: var(--color-text-muted);
}
.empty-resume p { margin: 0 0 var(--space-4); font-size: var(--font-size-sm); }
.empty-resume .el-button { margin: 0 6px; }

.upload-text { color: var(--color-text-muted); margin-top: var(--space-2); font-size: var(--font-size-sm); }
.upload-row { margin-top: var(--space-4); display: flex; align-items: center; gap: var(--space-3); }

.avatar-edit-row {
  display: flex;
  gap: var(--space-2);
  width: 100%;
}

/* el-descriptions 表格边框（与公司详情一致） */
.section-card :deep(.el-descriptions__label) {
  font-weight: 500;
  color: var(--color-text-secondary);
  background: var(--color-bg-alt);
}
.section-card :deep(.el-descriptions__body .el-descriptions__table td),
.section-card :deep(.el-descriptions__body .el-descriptions__table th) {
  border-color: var(--color-border-strong) !important;
}
</style>
