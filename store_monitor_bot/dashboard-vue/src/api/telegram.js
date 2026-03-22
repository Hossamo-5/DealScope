import api from './axios'

async function csrfHeaders() {
  const csrf = await api.get('/api/csrf-token')
  return { 'X-CSRF-Token': csrf.data.csrf_token }
}

export function resolveTelegram(input) {
  return api.post('/api/telegram/resolve', { input })
}

export function getGroups() {
  return api.get('/api/groups')
}

export async function createGroup(payload) {
  return api.post('/api/groups', payload, {
    headers: await csrfHeaders(),
  })
}

export async function updateGroup(id, payload) {
  return api.put(`/api/groups/${id}`, payload, {
    headers: await csrfHeaders(),
  })
}

export async function deleteGroup(id) {
  return api.delete(`/api/groups/${id}`, {
    headers: await csrfHeaders(),
  })
}

export async function testGroup(id) {
  return api.post(`/api/groups/${id}/test`, {}, {
    headers: await csrfHeaders(),
  })
}

export function getBotSettings() {
  return api.get('/api/settings/bot')
}

export async function saveBotSettings(payload) {
  return api.post('/api/settings/bot', payload, {
    headers: await csrfHeaders(),
  })
}

export async function testBotConnection() {
  return api.post('/api/bot-menu/test-connection')
}
