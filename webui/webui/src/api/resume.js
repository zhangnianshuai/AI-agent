import api from './index'

export function uploadResumeFile(formData) {
  return api.post('/resume/uploadFile', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function deleteResumeFile() {
  return api.delete('/resume/deleteFile')
}

export function loadResume() {
  return api.get('/resume/load')
}

export function uploadResume(data) {
  return api.post('/resume/upload', data)
}

export function getResume() {
  return api.get('/resume/getResume')
}
