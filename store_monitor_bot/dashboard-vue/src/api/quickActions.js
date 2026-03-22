import api from './axios'

export async function publishManualOpportunity(payload) {
  const csrf = await api.get('/api/csrf-token')
  return api.post('/api/opportunities/manual', payload, {
    headers: { 'X-CSRF-Token': csrf.data.csrf_token },
  })
}

export async function sendBroadcast(payload) {
  const csrf = await api.get('/api/csrf-token')
  return api.post('/api/broadcast', payload, {
    headers: { 'X-CSRF-Token': csrf.data.csrf_token },
  })
}
