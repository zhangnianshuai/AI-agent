<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getCompanyDetail, deleteCompany, updateCompany, uploadCompanyLogo, listCompanyPhotos, uploadCompanyPhoto, deleteCompanyPhoto } from '@/api/company'
import { searchJobs } from '@/api/job'
import { useAuthStore } from '@/stores/auth'
import { formatSalary } from '@/utils'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Edit, Delete, Upload, Plus, Picture, Location } from '@element-plus/icons-vue'
import defaultLogo from '@/assets/company/default_company_image.png'

const auth = useAuthStore()
const canEdit = computed(() => auth.isHR || auth.isAdmin)

const route = useRoute()
const router = useRouter()
const companyId = route.params.id

const company = ref(null)
const loading = ref(true)
const editing = ref(false)
const saving = ref(false)

const form = reactive({
  name: '', short_name: '', industry: '', scale: '',
  description: '', address: '', website: '', logo_url: '',
  contact_person: '', contact_phone: '',
})

const scales = ['少于50人', '50-150人', '150-500人', '500-2000人', '2000人以上']
const industries = ['互联网/IT', '金融', '教育', '医疗', '制造', '零售', '房地产', '物流', '其他']

async function fetchCompany() {
  loading.value = true
  try {
    company.value = await getCompanyDetail(companyId)
  } catch { company.value = null }
  finally { loading.value = false }
}

function startEdit() {
  const c = company.value
  form.name = c.name || ''
  form.short_name = c.short_name || ''
  form.industry = c.industry || ''
  form.scale = c.scale || ''
  form.description = c.description || ''
  form.address = c.address || ''
  form.website = c.website || ''
  form.logo_url = c.logo_url || ''
  form.contact_person = c.contact_person || ''
  form.contact_phone = c.contact_phone || ''
  editing.value = true
}

const logoSrc = computed(() => company.value?.logo_url || defaultLogo)

function onLogoError(e) {
  e.target.src = defaultLogo
}

const logoUploading = ref(false)
async function handleLogoUpload(file) {
  logoUploading.value = true
  try {
    const res = await uploadCompanyLogo(companyId, file)
    form.logo_url = res.url || form.logo_url
    ElMessage.success('Logo 上传成功')
  } catch { /* handled */ }
  finally { logoUploading.value = false }
}

function cancelEdit() { editing.value = false }

// ── 公司环境照片 ──
const photos = ref([])
const photoUploading = ref(false)

async function fetchPhotos() {
  try { photos.value = await listCompanyPhotos(companyId) || [] } catch { photos.value = [] }
}

async function handlePhotoUpload(f) {
  photoUploading.value = true
  try {
    await uploadCompanyPhoto(companyId, f)
    ElMessage.success('照片上传成功')
    await fetchPhotos()
  } catch { /* handled */ }
  finally { photoUploading.value = false }
}

async function handlePhotoDelete(photo) {
  try {
    await ElMessageBox.confirm('确定删除该照片？', '确认', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
    await deleteCompanyPhoto(companyId, photo.name)
    ElMessage.success('已删除')
    await fetchPhotos()
  } catch { /* cancelled */ }
}

async function handleSave() {
  saving.value = true
  try {
    await updateCompany(companyId, { ...form, company_id: companyId })
    ElMessage.success('公司信息已更新')
    editing.value = false
    await fetchCompany()
  } catch { /* handled */ }
  finally { saving.value = false }
}

async function handleDelete() {
  try {
    await ElMessageBox.confirm('删除公司将同时清除所有关联岗位和题库数据，不可恢复！确定继续？', '确认删除', {
      type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消',
    })
    await deleteCompany(companyId)
    ElMessage.success('公司已删除')
    router.push('/companies')
  } catch { /* cancelled */ }
}

// ── 公司岗位列表 ──
const jobs = ref([])
const jobsLoading = ref(false)

async function fetchJobs() {
  jobsLoading.value = true
  try {
    const data = await searchJobs({ company_id: companyId, page: 1, page_size: 20 })
    jobs.value = data.items || []
  } catch { jobs.value = [] }
  finally { jobsLoading.value = false }
}

function goJobDetail(jobId) {
  router.push(`/jobs/${jobId}`)
}

onMounted(() => { fetchCompany(); fetchPhotos(); fetchJobs() })
</script>

<template>
  <div class="company-detail" v-loading="loading">
    <template v-if="company">
      <!-- View Mode -->
      <el-card v-if="!editing" class="overview-card">
        <template #header>
          <div class="card-header">
            <span class="header-label">公司信息</span>
            <div class="header-right">
              <el-tag v-if="canEdit" :type="company.status === 1 ? 'success' : 'info'" size="small">
                {{ company.status === 1 ? '正常' : '停用' }}
              </el-tag>
              <template v-if="canEdit">
                <el-button size="small" :icon="Edit" @click="startEdit">编辑</el-button>
                <el-button size="small" type="danger" :icon="Delete" plain @click="handleDelete">删除</el-button>
              </template>
            </div>
          </div>
        </template>

        <div class="company-body">
          <!-- 上半部分：logo + 基本信息 -->
          <div class="company-top">
            <div class="logo-side">
              <img :src="logoSrc" class="company-logo" @error="onLogoError" />
            </div>
            <div class="info-side">
              <h2 class="company-name">{{ company.name }}</h2>
              <div class="info-grid">
                <div class="info-item" v-if="company.short_name">
                  <span class="info-label">简称</span>
                  <span class="info-value">{{ company.short_name }}</span>
                </div>
                <div class="info-item" v-if="company.industry">
                  <span class="info-label">行业</span>
                  <span class="info-value">{{ company.industry }}</span>
                </div>
                <div class="info-item" v-if="company.scale">
                  <span class="info-label">规模</span>
                  <span class="info-value">{{ company.scale }}</span>
                </div>
                <div class="info-item" v-if="company.address">
                  <span class="info-label">地址</span>
                  <span class="info-value">{{ company.address }}</span>
                </div>
                <div class="info-item" v-if="company.contact_person">
                  <span class="info-label">联系人</span>
                  <span class="info-value">{{ company.contact_person }}</span>
                </div>
                <div class="info-item" v-if="company.contact_phone">
                  <span class="info-label">电话</span>
                  <span class="info-value">{{ company.contact_phone }}</span>
                </div>
                <div class="info-item info-item-full" v-if="company.website">
                  <span class="info-label">官网</span>
                  <a class="info-value info-link" :href="company.website" target="_blank">{{ company.website }}</a>
                </div>
              </div>
            </div>
          </div>

          <!-- 下半部分：公司简介 -->
          <div v-if="company.description" class="company-desc-section">
            <h4 class="desc-title">公司简介</h4>
            <p class="desc-text">{{ company.description }}</p>
          </div>
        </div>

        <!-- 公司环境照片（只读） -->
        <div class="photo-section" v-if="photos.length">
          <div class="photo-header">
            <h4><el-icon><Picture /></el-icon> 公司环境</h4>
            <span class="photo-count">{{ photos.length }}/10</span>
          </div>
          <div class="photo-carousel">
            <el-carousel :interval="4000" arrow="always" height="100%">
              <el-carousel-item v-for="p in photos" :key="p.name">
                <img :src="p.url" class="carousel-img" />
              </el-carousel-item>
            </el-carousel>
          </div>
        </div>
      </el-card>

      <!-- Edit Mode -->
      <el-card v-else class="overview-card edit-card">
        <template #header>
          <div class="card-header">
            <h2>编辑公司信息</h2>
          </div>
        </template>
        <el-form :model="form" label-width="90px">
          <el-row :gutter="16">
            <el-col :span="12"><el-form-item label="公司名称"><el-input v-model="form.name" /></el-form-item></el-col>
            <el-col :span="12"><el-form-item label="公司简称"><el-input v-model="form.short_name" /></el-form-item></el-col>
          </el-row>
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="行业">
                <el-select v-model="form.industry" style="width:100%" clearable>
                  <el-option v-for="t in industries" :key="t" :label="t" :value="t" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="规模">
                <el-select v-model="form.scale" style="width:100%" clearable>
                  <el-option v-for="s in scales" :key="s" :label="s" :value="s" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="16">
            <el-col :span="12"><el-form-item label="地址"><el-input v-model="form.address" /></el-form-item></el-col>
            <el-col :span="12"><el-form-item label="官网"><el-input v-model="form.website" /></el-form-item></el-col>
          </el-row>
          <el-row :gutter="16">
            <el-col :span="12"><el-form-item label="联系人"><el-input v-model="form.contact_person" /></el-form-item></el-col>
            <el-col :span="12"><el-form-item label="联系电话"><el-input v-model="form.contact_phone" /></el-form-item></el-col>
          </el-row>
          <el-form-item label="公司 Logo">
            <div class="logo-edit-row">
              <el-input v-model="form.logo_url" placeholder="输入图片URL 或 上传文件" style="flex:1" />
              <el-upload
                :show-file-list="false"
                :before-upload="(f) => { handleLogoUpload(f); return false }"
                accept="image/*"
              >
                <el-button :icon="Upload" :loading="logoUploading">上传</el-button>
              </el-upload>
            </div>
          </el-form-item>
          <el-form-item label="公司简介"><el-input v-model="form.description" type="textarea" :rows="4" /></el-form-item>
          <el-form-item>
            <el-button @click="cancelEdit">取消</el-button>
            <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
          </el-form-item>
        </el-form>

        <!-- 编辑模式下可管理照片 -->
        <div class="photo-section">
          <div class="photo-header">
            <h4><el-icon><Picture /></el-icon> 公司环境</h4>
            <el-upload
              :show-file-list="false"
              :before-upload="(f) => { handlePhotoUpload(f); return false }"
              accept="image/*"
              :disabled="photos.length >= 10"
            >
              <el-button size="small" :icon="Plus" :loading="photoUploading" :disabled="photos.length >= 10">
                上传 {{ photos.length }}/10
              </el-button>
            </el-upload>
          </div>
          <div class="photo-carousel" v-if="photos.length">
            <el-carousel :interval="4000" arrow="always" height="100%">
              <el-carousel-item v-for="p in photos" :key="p.name">
                <img :src="p.url" class="carousel-img" />
                <el-button class="photo-del" type="danger" :icon="Delete" size="small" circle plain @click.stop="handlePhotoDelete(p)" />
              </el-carousel-item>
            </el-carousel>
          </div>
          <p v-else class="photo-empty">暂无环境照片，点击上传</p>
        </div>
      </el-card>

    </template>

    <!-- ── 公司岗位列表 ── -->
    <div class="company-jobs-section" v-if="company">
      <h3 class="jobs-section-title">
        在招职位
        <span class="jobs-count-badge">{{ jobs.length }}</span>
      </h3>
      <div class="jobs-list-card" v-loading="jobsLoading">
        <template v-if="jobs.length">
          <div
            v-for="job in jobs"
            :key="job.job_id"
            class="job-card-item"
            @click="goJobDetail(job.job_id)"
          >
            <div class="jci-row jci-row-top">
              <h4 class="jci-title">{{ job.title }}</h4>
              <span class="jci-salary">{{ formatSalary(job.salary_min, job.salary_max) }}</span>
            </div>
            <div class="jci-row jci-row-bottom">
              <div class="jci-tags">
                <span v-if="job.location" class="jci-tag">
                  <el-icon :size="12"><Location /></el-icon>
                  {{ job.location }}
                </span>
                <span v-if="job.category" class="jci-tag jci-tag-cat">{{ job.category }}</span>
                <span v-if="job.education_requirement" class="jci-tag">{{ job.education_requirement }}</span>
                <span v-if="job.experience_requirement" class="jci-tag">{{ job.experience_requirement }}</span>
              </div>
              <span class="jci-view">查看详情 →</span>
            </div>
          </div>
        </template>
        <el-empty v-else-if="!jobsLoading" description="暂无在招职位" :image-size="48" />
      </div>
    </div>

    <el-empty v-else-if="!loading" description="公司不存在" />
  </div>
</template>

<style scoped>
.company-detail { width: 100%; max-width: 900px; }

/* ---- Card ---- */
.overview-card {
  margin-bottom: var(--space-4);
  border-radius: var(--radius-lg);
  box-shadow: 0 1px 3px rgba(0,0,0,.06);
}

/* ---- Header ---- */
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header .header-label {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--color-text-secondary);
  letter-spacing: .5px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

/* ---- Body Layout ---- */
.company-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

/* ── Top section: logo + info ── */
.company-top {
  display: flex;
  gap: var(--space-8);
}

.logo-side {
  flex-shrink: 0;
  width: 160px;
}

.company-logo {
  width: 160px;
  height: 200px;
  border-radius: var(--radius-lg);
  object-fit: cover;
  border: 1px solid var(--color-border);
  background: var(--color-bg-alt);
}

.info-side {
  flex: 1;
  min-width: 0;
}

.company-name {
  margin: 0 0 var(--space-4);
  font-size: 22px;
  font-weight: 700;
  color: var(--color-text);
  letter-spacing: .3px;
}

/* Info grid — 2 columns with borders */
.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.info-item {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--color-border);
  border-right: 1px solid var(--color-border);
}

/* 每行第二列去掉右边框，最后一行的项目去掉底边框 */
.info-item:nth-child(2n) {
  border-right: none;
}

.info-item-full {
  grid-column: 1 / -1;
  border-right: none !important;
}

.info-item:nth-last-child(-n+2) {
  border-bottom: none;
}

.info-label {
  font-size: 13px;
  color: var(--color-text-muted);
  flex-shrink: 0;
  min-width: 40px;
}

.info-value {
  font-size: 14px;
  color: var(--color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.info-link {
  color: var(--color-primary);
  text-decoration: none;
}

.info-link:hover {
  text-decoration: underline;
}

/* ── Bottom section: description ── */
.company-desc-section {
  padding: var(--space-4) var(--space-5);
  background: var(--color-bg-alt);
  border-radius: var(--radius-md);
  border-left: 3px solid var(--color-primary);
}

.desc-title {
  margin: 0 0 var(--space-2);
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
}

.desc-text {
  margin: 0;
  color: var(--color-text-secondary);
  line-height: 1.8;
  font-size: 14px;
}

/* ---- Edit Form ---- */
.edit-card :deep(.el-card__header) {
  padding: var(--space-4) var(--space-6);
}

.logo-edit-row {
  display: flex;
  gap: var(--space-2);
  width: 100%;
}

/* ---- Photo Gallery ---- */
.photo-section {
  margin-top: var(--space-5);
  padding-top: var(--space-4);
  border-top: 1px solid var(--color-border);
}

.photo-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-3);
}

.photo-header h4 {
  margin: 0;
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--color-text);
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.photo-count {
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
}

.photo-carousel {
  border-radius: var(--radius-md);
  overflow: hidden;
  border: 1px solid var(--color-border);
  aspect-ratio: 16 / 9;
}

.photo-carousel :deep(.el-carousel),
.photo-carousel :deep(.el-carousel__container),
.photo-carousel :deep(.el-carousel__item) {
  height: 100% !important;
}

.carousel-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.photo-del {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 2;
  opacity: 0.85;
}

.photo-empty {
  text-align: center;
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
  padding: var(--space-4);
  margin: 0;
}

/* ── Company Jobs Section ── */
.company-jobs-section {
  width: 100%;
  margin-top: var(--space-4);
}

.jobs-section-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--color-text);
  margin: 0 0 12px 0;
  padding-left: 10px;
  border-left: 3px solid var(--color-primary);
  display: flex;
  align-items: center;
  gap: 8px;
}

.jobs-count-badge {
  font-size: 12px;
  font-weight: 500;
  color: var(--color-primary);
  background: var(--color-primary-bg, #EFF6FF);
  padding: 2px 10px;
  border-radius: 999px;
}

.jobs-list-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.job-card-item {
  padding: 16px 20px;
  border-bottom: 1px solid #F3F4F6;
  cursor: pointer;
  transition: all 0.2s ease;
}

.job-card-item:last-child {
  border-bottom: none;
}

.job-card-item:hover {
  background: #F9FAFB;
}

.job-card-item:hover .jci-title {
  color: var(--color-primary);
}

.jci-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.jci-row-top {
  margin-bottom: 8px;
}

.jci-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition: color 0.2s ease;
}

.jci-salary {
  font-size: 17px;
  font-weight: 700;
  color: #EF4444;
  white-space: nowrap;
  flex-shrink: 0;
  margin-left: 16px;
}

.jci-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

.jci-tag {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 10px;
  border-radius: var(--radius-full);
  background: var(--color-bg-alt);
  color: var(--color-text-secondary);
  font-size: 12px;
  font-weight: 500;
}

.jci-tag-cat {
  background: var(--color-primary-bg, #EFF6FF);
  color: var(--color-primary);
}

.jci-view {
  font-size: 13px;
  color: var(--color-text-muted);
  white-space: nowrap;
  flex-shrink: 0;
  opacity: 0;
  transition: all 0.2s ease;
}

.job-card-item:hover .jci-view {
  opacity: 1;
  color: var(--color-primary);
}
</style>
