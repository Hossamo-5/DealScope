import api from './axios'

async function csrfHeaders() {
  const csrf = await api.get('/api/csrf-token')
  return { 'X-CSRF-Token': csrf.data.csrf_token }
}

export function getSettings(category) {
  return api.get(`/api/settings/${category}`)
}

export async function saveSettings(category, payload) {
  return api.post(`/api/settings/${category}`, payload, {
    headers: await csrfHeaders(),
  })
}

export function getSystemInfo() {
  return api.get('/api/settings/system/info')
}

export async function restartMonitor() {
  return api.post('/api/settings/system/restart-monitor', {}, {
    headers: await csrfHeaders(),
  })
}

export async function clearCache() {
  return api.post('/api/settings/system/clear-cache', {}, {
    headers: await csrfHeaders(),
  })
}

export async function testAiScraper(url) {
  return api.post('/api/settings/test-ai-scraper', { url }, {
    headers: await csrfHeaders(),
  })
}

export function exportData(type) {
  return api.get(`/api/settings/system/export/${type}`, {
    responseType: 'blob',
  })
}
