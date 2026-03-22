import api from './axios'

export function fetchStoreRequests(status = 'pending') {
  return api.get('/api/store-requests', { params: { status } })
}

export async function approveStoreRequest(id, admin_notes = '') {
  const csrf = await api.get('/api/csrf-token')
  return api.post(`/api/store-requests/${id}/approve`, { admin_notes }, {
    headers: { 'X-CSRF-Token': csrf.data.csrf_token },
  })
}

export async function rejectStoreRequest(id, admin_notes = '') {
  const csrf = await api.get('/api/csrf-token')
  return api.post(`/api/store-requests/${id}/reject`, { admin_notes }, {
    headers: { 'X-CSRF-Token': csrf.data.csrf_token },
  })
}
