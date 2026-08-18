import api from './index'

export function createJob(data) {
  return api.post('/job/create', data)
}

export function searchJobs(params) {
  return api.post('/job/search', params)
}

export function aiSearchJobs() {
  return api.get('/job/ai_search')
}

export function getJobDetail(jobId) {
  return api.get(`/job/detail/${jobId}`)
}

export function uploadQuestionFile(formData) {
  formData.append('category', 'question_bank')
  return api.post('/file/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function insertQuestion(data) {
  return api.post('/job/insert_question', data)
}

export function getQuestions(params) {
  return api.get('/job/get_question', { params })
}

export function updateQuestion(data) {
  return api.put('/job/update_question', data)
}

export function deleteQuestion(data) {
  return api.delete('/job/delete_question', { data })
}

export function updateJob(jobId, data) {
  return api.put(`/job/update/${jobId}`, data)
}

export function onlineJob(jobId) {
  return api.put(`/job/online/${jobId}`)
}

export function offlineJob(jobId) {
  return api.put(`/job/offline/${jobId}`)
}

export function deleteJob(jobId) {
  return api.delete(`/job/${jobId}`)
}
