<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import {
  getQuestions,
  insertQuestion,
  updateQuestion,
  deleteQuestion,
  uploadQuestionFile,
} from '@/api/job'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled, Plus } from '@element-plus/icons-vue'

const route = useRoute()
const jobId = route.params.id

const questions = ref([])
const total = ref(0)
const loading = ref(false)

const page = ref(1)
const pageSize = ref(10)

// Upload dialog
const uploadVisible = ref(false)
const uploadCompanyId = ref('')
const uploadFileList = ref([])
const uploading = ref(false)

// Edit dialog
const editVisible = ref(false)
const editing = ref(false)
const editForm = reactive({
  pk: '',
  question: '',
  answer: '',
  scoring_criteria: '',
  difficulty: 1,
})

const formRef = ref(null)

async function fetchQuestions() {
  loading.value = true
  try {
    const data = await getQuestions({
      company_id: uploadCompanyId.value || undefined,
      job_id: jobId,
      page: page.value,
      page_size: pageSize.value,
    })
    questions.value = data.items || []
    total.value = data.total || 0
  } catch {
    // Handled by interceptor
  } finally {
    loading.value = false
  }
}

function handlePageChange(p) {
  page.value = p
  fetchQuestions()
}

// Upload
function openUpload() {
  uploadFileList.value = []
  uploadVisible.value = true
}

async function handleUpload() {
  if (!uploadCompanyId.value || !uploadFileList.value.length) {
    ElMessage.warning('请选择公司并上传文件')
    return
  }

  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('company_id', uploadCompanyId.value)
    formData.append('job_id', jobId)
    formData.append('file', uploadFileList.value[0].raw)
    await uploadQuestionFile(formData)
    await insertQuestion({ company_id: uploadCompanyId.value, job_id: jobId })
    ElMessage.success('题库导入成功')
    uploadVisible.value = false
    fetchQuestions()
  } catch {
    // Handled by interceptor
  } finally {
    uploading.value = false
  }
}

// Edit
function openEdit(row) {
  if (row) {
    editForm.pk = row.pk
    editForm.question = row.question
    editForm.answer = row.answer
    editForm.scoring_criteria = row.scoring_criteria
    editForm.difficulty = row.difficulty || 1
  } else {
    editForm.pk = ''
    editForm.question = ''
    editForm.answer = ''
    editForm.scoring_criteria = ''
    editForm.difficulty = 1
  }
  editVisible.value = true
}

async function handleEdit() {
  editing.value = true
  try {
    await updateQuestion({
      company_id: uploadCompanyId.value,
      pk: editForm.pk,
      question: editForm.question,
      answer: editForm.answer,
      scoring_criteria: editForm.scoring_criteria,
      difficulty: editForm.difficulty,
    })
    ElMessage.success('更新成功')
    editVisible.value = false
    fetchQuestions()
  } catch {
    // Handled by interceptor
  } finally {
    editing.value = false
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定要删除该试题吗？`, '确认删除', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await deleteQuestion({
      company_id: uploadCompanyId.value,
      pk: row.pk,
    })
    ElMessage.success('删除成功')
    fetchQuestions()
  } catch {
    // User cancelled or error
  }
}

onMounted(() => {
  // Try to fetch if company_id is known
})
</script>

<template>
  <div class="question-manage">
    <div class="page-header">
      <h1 class="page-title">题库管理</h1>
      <div>
        <el-button type="primary" :icon="UploadFilled" @click="openUpload">导入题库</el-button>
      </div>
    </div>

    <!-- Company ID input -->
    <el-card class="filter-card">
      <el-form inline>
        <el-form-item label="公司ID">
          <el-input v-model="uploadCompanyId" placeholder="请输入公司ID" style="width: 200px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchQuestions" :disabled="!uploadCompanyId">
            查询题库
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- Question list -->
    <el-card>
      <el-table :data="questions" v-loading="loading" stripe>
        <el-table-column prop="question" label="题目" min-width="200" show-overflow-tooltip />
        <el-table-column prop="answer" label="参考答案" min-width="150" show-overflow-tooltip />
        <el-table-column prop="difficulty" label="难度" width="80" />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="openEdit(row)">编辑</el-button>
            <el-button type="danger" link @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrap" v-if="total > pageSize">
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="total"
          background
          layout="prev, pager, next"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>

    <!-- Upload dialog -->
    <el-dialog v-model="uploadVisible" title="导入题库" width="500px">
      <el-form>
        <el-form-item label="公司ID">
          <el-input v-model="uploadCompanyId" placeholder="请输入公司ID" />
        </el-form-item>
        <el-form-item label="题库文件">
          <el-upload
            v-model:file-list="uploadFileList"
            :limit="1"
            accept=".doc,.docx"
            :auto-upload="false"
            drag
          >
            <el-icon :size="40"><UploadFilled /></el-icon>
            <div>拖拽或点击上传 .doc/.docx 文件</div>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="uploadVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="handleUpload">上传并解析</el-button>
      </template>
    </el-dialog>

    <!-- Edit dialog -->
    <el-dialog v-model="editVisible" title="编辑试题" width="600px">
      <el-form ref="formRef" :model="editForm" label-position="top">
        <el-form-item label="题目">
          <el-input v-model="editForm.question" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="参考答案">
          <el-input v-model="editForm.answer" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="评分标准">
          <el-input v-model="editForm.scoring_criteria" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="难度">
          <el-input-number v-model="editForm.difficulty" :min="1" :max="5" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="editing" @click="handleEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.question-manage {
  max-width: 1100px;
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
}

.filter-card {
  margin-bottom: var(--space-4);
}

.pagination-wrap {
  display: flex;
  justify-content: center;
  margin-top: var(--space-6);
}
</style>
