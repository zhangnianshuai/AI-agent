import api from './index'

export function login(data) {
  return api.post('/user/login', data)
}

export function register(data) {
  return api.post('/user/register', data)
}

export function getMe() {
  return api.get('/user/me')
}

export function updateProfile(data) {
  return api.put('/user/profile', data)
}

export function updatePassword(data) {
  return api.put('/user/password', data)
}

export function uploadAvatar(file) {
  const form = new FormData()
  form.append('category', 'avatar')
  form.append('file', file)
  return api.post('/file/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}
