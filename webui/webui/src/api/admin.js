import api from './index'

export function updateUserRole(data) {
  return api.post('/admin/user/role', data)
}

export function updateUserStatus(data) {
  return api.post('/admin/user/status', data)
}

export function listUsers(params) {
  return api.get('/admin/users', { params })
}
