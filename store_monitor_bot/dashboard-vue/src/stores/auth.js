import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as apiLogin, logout as apiLogout } from '../api/auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || sessionStorage.getItem('token') || '')
  const rememberMe = ref(localStorage.getItem('sm_remember') === '1')
  const telegramId = ref(localStorage.getItem('sm_tid') || '')
  const isAuthenticated = computed(() => !!token.value)

  function setToken(t, remember = false) {
    token.value = t
    rememberMe.value = remember
    localStorage.setItem('sm_remember', remember ? '1' : '0')
    if (remember) {
      localStorage.setItem('sm_token', t)
      localStorage.setItem('token', t)
      sessionStorage.removeItem('sm_token')
      sessionStorage.removeItem('token')
    } else {
      sessionStorage.setItem('sm_token', t)
      sessionStorage.setItem('token', t)
      localStorage.removeItem('sm_token')
      localStorage.removeItem('token')
    }
  }

  async function login(credentials, remember = false) {
    const { data } = await apiLogin(credentials)
    if (credentials?.telegram_id) {
      telegramId.value = String(credentials.telegram_id)
      localStorage.setItem('sm_tid', String(credentials.telegram_id))
    }
    setToken(data.access_token, remember)
    return data
  }

  async function refreshToken() {
    if (!telegramId.value) return false
    const { data } = await apiLogin({ telegram_id: parseInt(telegramId.value, 10) })
    setToken(data.access_token, rememberMe.value)
    return true
  }

  async function logout() {
    try {
      await apiLogout()
    } catch (_err) {
      // ignore network/logout failures and clear client session anyway
    }
    token.value = ''
    localStorage.removeItem('sm_token')
    localStorage.removeItem('token')
    sessionStorage.removeItem('sm_token')
    sessionStorage.removeItem('token')
    localStorage.removeItem('sm_remember')
    localStorage.removeItem('sm_tid')
    telegramId.value = ''
  }

  if (!token.value) {
    token.value = sessionStorage.getItem('token') || localStorage.getItem('token') || ''
  }

  return { token, rememberMe, telegramId, isAuthenticated, login, refreshToken, logout }
})
