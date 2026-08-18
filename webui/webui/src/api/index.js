import axios from 'axios'
import { getToken, removeToken } from '@/utils'
import { ElMessage } from 'element-plus'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
  // Preserve 64-bit Snowflake IDs as strings (JS Number loses precision beyond 2^53)
  transformResponse: [function (data) {
    if (typeof data === 'string') {
      // Quote integers with 16+ digits so JSON.parse treats them as strings
      const safe = data.replace(/: *\b(\d{16,})\b/g, ': "$1"')
      return JSON.parse(safe)
    }
    return data
  }],
})

// Request interceptor — attach Bearer token
api.interceptors.request.use(
  (config) => {
    const token = getToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor — unwrap Result envelope
api.interceptors.response.use(
  (response) => {
    const res = response.data
    // FastAPI returns { code, message, data }
    if (res.code !== undefined && res.code !== 200 && res.code !== 0) {
      ElMessage.error(res.message || '请求失败')
      return Promise.reject(new Error(res.message || '请求失败'))
    }
    // Return the data field directly, or the whole response if no code field
    return res.data !== undefined ? res.data : res
  },
  (error) => {
    if (error.response) {
      const { status } = error.response
      if (status === 401) {
        removeToken()
        ElMessage.error('登录已过期，请重新登录')
        window.location.href = '/login'
      } else if (status === 403) {
        ElMessage.error('没有权限执行此操作')
      } else {
        ElMessage.error(error.response.data?.message || `请求错误 ${status}`)
      }
    } else {
      ElMessage.error('网络错误，请检查连接')
    }
    return Promise.reject(error)
  }
)

export default api
