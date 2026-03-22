import api from './axios'

export function fetchUsers(params = {}) {
  return api.get('/api/users', { params: { include_sensitive: 1, ...params } })
}

export function fetchUserDetail(telegramId) {
  return api.get(`/api/users/${telegramId}`)
}

export function fetchUserProfile(telegramId) {
  return api.get(`/api/users/${telegramId}/profile`)
}

export function fetchUserActivity(telegramId, params = {}) {
  return api.get(`/api/users/${telegramId}/activity`, { params })
}

export async function upgradeUser(telegramId, plan, days) {
  const csrf = await api.get('/api/csrf-token')
  return api.post(
    `/api/users/${telegramId}/upgrade`,
    { plan, days },
    { headers: { 'X-CSRF-Token': csrf.data.csrf_token } }
  )
}

export async function banUser(telegramId) {
  const csrf = await api.get('/api/csrf-token')
  return api.post(`/api/users/${telegramId}/ban`, {}, {
    headers: { 'X-CSRF-Token': csrf.data.csrf_token },
  })
}

export async function unbanUser(telegramId) {
  const csrf = await api.get('/api/csrf-token')
  return api.post(`/api/users/${telegramId}/unban`, {}, {
    headers: { 'X-CSRF-Token': csrf.data.csrf_token },
  })
}

export async function sendMessageToUser(telegramId, message) {
  const csrf = await api.get('/api/csrf-token')
  return api.post(`/api/users/${telegramId}/send-message`, { message }, {
    headers: { 'X-CSRF-Token': csrf.data.csrf_token },
  })
}

export async function toggleBanUser(telegramId, isBanned) {
  return isBanned ? unbanUser(telegramId) : banUser(telegramId)
}
