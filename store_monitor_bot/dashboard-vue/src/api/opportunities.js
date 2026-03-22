import api from './axios'

export function fetchOpportunities(status = 'new', limit = 20, offset = 0) {
  return api.get('/api/opportunities', { params: { status, limit, offset } })
}

export async function approveOpportunity(id, body = {}) {
  const csrf = await api.get('/api/csrf-token')
  return api.post(`/api/opportunities/${id}/approve`, body, {
    headers: { 'X-CSRF-Token': csrf.data.csrf_token },
  })
}
