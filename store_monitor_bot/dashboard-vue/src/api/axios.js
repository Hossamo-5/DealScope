import axios from 'axios'
import { useAuthStore } from '../stores/auth'
import router from '../router'

const api = axios.create({
  baseURL: '/',
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  // Try multiple token storage locations
  const token = localStorage.getItem('access_token') ||
                localStorage.getItem('sm_token') ||
                localStorage.getItem('token') ||
                sessionStorage.getItem('token')

  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (res) => res,
  async (err) => {
    if (err.response && err.response.status === 401) {
      const auth = useAuthStore()
      const original = err.config || {}

      if ((original.url || '').includes('/auth/login')) {
        return Promise.reject(err)
      }

      if (!original._retry) {
        original._retry = true
        try {
          const refreshed = await auth.refreshToken()
          if (refreshed) {
            original.headers = original.headers || {}
            original.headers.Authorization = `Bearer ${auth.token}`
            return api(original)
          }
        } catch (_refreshErr) {
          // fallback to logout flow below
        }
      }

      await auth.logout()
      router.push('/login')
    }
    return Promise.reject(err)
  }
)

export default api
