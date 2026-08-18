<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  getQuestions, insertQuestion, updateQuestion, deleteQuestion, uploadQuestionFile,
} from '@/api/job'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled, Plus, ArrowLeft, Edit, Delete } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const companyId = route.params.id
const jobId = route.params.jobId

const questions = ref([])
const total = ref(0)
const loading = ref(false)
const page = ref(1)
const pageSize = ref(10)

// Upload dialog
const uploadVisible = ref(false)
const uploadFileList = ref([])
const uploading = ref(false)

// Edit / Insert dialog
const editVisible = ref(false)
const saving = ref(false)
const isInsert = ref(false)
const editForm = reactive({
  pk: '', question: '', answer: '', scoring_criteria: '', difficulty: 3,
})

async function fetchQuestions() {
  loading.value = true
  try {
    const data = await getQuestions({
      company_id: companyId, job_id: jobId,
      page: page.value, page_size: pageSize.value,
    })
    questions.value = data.items || []
    total.value = data.total || 0
  } catch { questions.value = [] }
  finally { loading.value = false }
}

// Upload
function openUpload() {
  uploadFileList.value = []
  uploadVisible.value = true
}

async function handleUpload() {
  if (!uploadFileList.value.length) { ElMessage.warning('请上传文件'); return }
  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('company_id', companyId)
    formData.append('job_id', jobId)
    formData.append('file', uploadFileList.value[0].raw)
    await uploadQuestionFile(formData)
    await insertQuestion({ company_id: companyId, job_id: jobId })
    ElMessage.success('题库导入成功')
    uploadVisible.value = false
    fetchQuestions()
  } catch { /* handled */ }
  finally { uploading.value = false }
}

// Insert / Edit
function openInsert() {
  editForm.pk = ''
  editForm.question = ''
  editForm.answer = ''
  editForm.scoring_criteria = ''
  editForm.difficulty = 3
  isInsert.value = true
  editVisible.value = true
}

function openEdit(row) {
  editForm.pk = row.pk
  editForm.question = row.question
  editForm.answer = row.answer
  editForm.scoring_criteria = row.scoring_criteria || ''
  editForm.difficulty = row.difficulty || 3
  isInsert.value = false
  editVisible.value = true
}

async function handleSave() {
  saving.value = true
  try {
    if (isInsert.value) {
      // Manual insert: first add to Milvus via insert_question endpoint
      // But insert_question reads from file, not manual data
      // We need to use update_question with a generated pk
      ElMessage.warning('手动插入需通过上传 Word 文档方式，请使用导入题库功能')
      saving.value = false
      return
    }
    await updateQuestion({
      company_id: companyId, pk: editForm.pk,
      question: editForm.question, answer: editForm.answer,
      scoring_criteria: editForm.scoring_criteria, difficulty: editForm.difficulty,
    })
    ElMessage.success('更新成功')
    editVisible.value = false
    fetchQuestions()
  } catch { /* handled */ }
  finally { saving.value = false }
}

// Detail dialog
const detailVisible = ref(false)
const detailRow = ref(null)

function openDetail(row) {
  detailRow.value = row
  detailVisible.value = true
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm('确定要删除该试题吗？', '确认删除', {
      type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消',
    })
    await deleteQuestion({ company_id: companyId, pk: row.pk })
    ElMessage.success('删除成功')
    fetchQuestions()
  } catch { /* cancelled */ }
}

onMounted(() => { fetchQuestions() })
</script>

<template>
  <div class="qb-questions">
    <div class="page-header">
      <div class="header-left">
        <el-button :icon="ArrowLeft" @click="router.push(`/companies/${companyId}/questions`)">返回岗位管理</el-button>
        <h1 class="page-title">题库题目</h1>
      </div>
      <div class="header-actions">
        <el-button type="success" :icon="Plus" @click="openInsert" disabled>手动添加（请使用导入）</el-button>
        <el-button type="primary" :icon="UploadFilled" @click="openUpload">导入题库</el-button>
      </div>
    </div>

    <el-card>
      <el-table :data="questions" v-loading="loading" stripe @row-click="openDetail" style="cursor: pointer">
        <el-table-column label="题目" min-width="200">
          <template #default="{ row }">
            <span class="cell-text">{{ row.question }}</span>
          </template>
        </el-table-column>
        <el-table-column label="参考答案" min-width="150">
          <template #default="{ row }">
            <span class="cell-text">{{ row.answer }}</span>
          </template>
        </el-table-column>
        <el-table-column label="评分标准" min-width="120">
          <template #default="{ row }">
            <span class="cell-text">{{ row.scoring_criteria || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="difficulty" label="难度" width="80" align="center" />
      </el-table>

      <div class="pagination-wrap" v-if="total > pageSize">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50]"
          :total="total"
          background
          layout="total, sizes, prev, pager, next"
          @current-change="fetchQuestions"
          @size-change="fetchQuestions"
        />
      </div>
    </el-card>

    <!-- Upload dialog -->
    <el-dialog v-model="uploadVisible" title="导入题库" width="500px">
      <p style="margin-bottom:12px;color:var(--color-text-secondary)">上传 .doc/.docx 文件，系统将自动解析并导入题库</p>
      <el-upload v-model:file-list="uploadFileList" :limit="1" accept=".doc,.docx" :auto-upload="false" drag>
        <el-icon :size="40"><UploadFilled /></el-icon>
        <div>拖拽或点击上传 .doc/.docx 文件</div>
      </el-upload>
      <template #footer>
        <el-button @click="uploadVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="handleUpload">上传并解析</el-button>
      </template>
    </el-dialog>

    <!-- Detail dialog -->
    <el-dialog v-model="detailVisible" title="题目详情" width="650px">
      <template v-if="detailRow">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="题目" label-class-name="detail-label">
            <div class="detail-text">{{ detailRow.question }}</div>
          </el-descriptions-item>
          <el-descriptions-item label="参考答案">
            <div class="detail-text">{{ detailRow.answer }}</div>
          </el-descriptions-item>
          <el-descriptions-item label="评分标准">
            <div class="detail-text">{{ detailRow.scoring_criteria || '无' }}</div>
          </el-descriptions-item>
          <el-descriptions-item label="难度">
            <el-rate v-model="detailRow.difficulty" disabled show-score text-color="#ff9900" />
          </el-descriptions-item>
        </el-descriptions>
      </template>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
        <el-button type="warning" :icon="Edit" @click="detailVisible = false; openEdit(detailRow)">编辑</el-button>
        <el-button type="danger" :icon="Delete" @click="detailVisible = false; handleDelete(detailRow)">删除</el-button>
      </template>
    </el-dialog>

    <!-- Edit dialog -->
    <el-dialog v-model="editVisible" :title="isInsert ? '新增试题' : '编辑试题'" width="600px">
      <el-form :model="editForm" label-position="top">
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
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.qb-questions { max-width: 1100px; }

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-4);
  flex-wrap: wrap;
  gap: var(--space-3);
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.header-actions {
  display: flex;
  gap: var(--space-2);
}

.page-title {
  font-size: var(--font-size-2xl);
  color: var(--color-text);
  margin: 0;
}

.detail-text {
  white-space: pre-wrap;
  line-height: 1.7;
  padding: var(--space-1) 0;
}

:deep(.detail-label) {
  font-weight: 600;
}

.cell-text {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pagination-wrap {
  display: flex;
  justify-content: center;
  margin-top: var(--space-6);
}
</style>
