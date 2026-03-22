import api from './axios'

export function login(payload) {
  return api.post('/auth/login', payload)
}

export function logout() {
  return api.post('/auth/logout')
}
