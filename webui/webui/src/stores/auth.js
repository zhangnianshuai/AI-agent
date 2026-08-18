import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as loginApi, register as registerApi, getMe as getMeApi, updateProfile as updateProfileApi, updatePassword as updatePasswordApi } from '@/api/user'
import { getToken, setToken, removeToken } from '@/utils'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const token = ref(getToken() || '')

  const isLoggedIn = computed(() => !!token.value)
  const role = computed(() => user.value?.role || '')
  const isAdmin = computed(() => role.value === 'admin')
  const isHR = computed(() => role.value === 'hr' || role.value === 'admin')

  async function login(credentials) {
    const data = await loginApi(credentials)
    token.value = data.token
    setToken(data.token)
    await fetchUser()
    return data
  }

  async function register(form) {
    const data = await registerApi(form)
    // Auto-login if backend returns token, otherwise just return
    if (data && data.token) {
      token.value = data.token
      setToken(data.token)
      await fetchUser()
    }
    return data
  }

  async function fetchUser() {
    try {
      const data = await getMeApi()
      user.value = data
      return data
    } catch (e) {
      logout()
      throw e  // re-throw so callers can distinguish success vs failure
    }
  }

  async function updateProfile(form) {
    const data = await updateProfileApi(form)
    user.value = { ...user.value, ...data }
    return data
  }

  async function updatePassword(form) {
    return await updatePasswordApi(form)
  }

  function logout() {
    token.value = ''
    user.value = null
    removeToken()
  }

  return {
    user,
    token,
    isLoggedIn,
    role,
    isAdmin,
    isHR,
    login,
    register,
    fetchUser,
    updateProfile,
    updatePassword,
    logout,
  }
})
