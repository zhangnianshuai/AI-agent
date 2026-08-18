import api from './index'

export function createCompany(data) {
  return api.post('/company/create', data)
}

export function listCompanies() {
  return api.get('/company/list')
}

export function listPublicCompanies() {
  return api.get('/company/public/list')
}

export function getCompanyDetail(companyId) {
  return api.get(`/company/${companyId}/detail`)
}

export function deleteCompany(companyId) {
  return api.delete(`/company/${companyId}`)
}

export function updateCompany(companyId, data) {
  return api.put(`/company/${companyId}`, data)
}

export function uploadCompanyLogo(companyId, file) {
  const form = new FormData()
  form.append('category', 'company_logo')
  form.append('file', file)
  form.append('company_id', companyId)
  return api.post('/file/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function listCompanyPhotos(companyId) {
  return api.get(`/company/${companyId}/photos`)
}

export function uploadCompanyPhoto(companyId, file) {
  const form = new FormData()
  form.append('category', 'company_photo')
  form.append('file', file)
  form.append('company_id', companyId)
  return api.post('/file/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function deleteCompanyPhoto(companyId, filename) {
  return api.delete(`/company/${companyId}/photos/${encodeURIComponent(filename)}`)
}
