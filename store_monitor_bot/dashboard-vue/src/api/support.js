import api from './axios'

export function fetchSupportTickets(params = {}) {
  return api.get('/api/support/tickets', { params })
}

export function fetchSupportTicket(ticketId) {
  return api.get(`/api/support/tickets/${ticketId}`)
}

export async function replyToSupportTicket(ticketId, message) {
  const csrf = await api.get('/api/csrf-token')
  return api.post(
    `/api/support/tickets/${ticketId}/reply`,
    { message },
    { headers: { 'X-CSRF-Token': csrf.data.csrf_token } }
  )
}

export async function assignSupportTicket(ticketId, adminId) {
  const csrf = await api.get('/api/csrf-token')
  return api.post(
    `/api/support/tickets/${ticketId}/assign`,
    { admin_id: adminId },
    { headers: { 'X-CSRF-Token': csrf.data.csrf_token } }
  )
}

export async function transferSupportTicket(ticketId, department, note = '') {
  const csrf = await api.get('/api/csrf-token')
  return api.post(
    `/api/support/tickets/${ticketId}/transfer`,
    { department, note },
    { headers: { 'X-CSRF-Token': csrf.data.csrf_token } }
  )
}

export async function resolveSupportTicket(ticketId) {
  const csrf = await api.get('/api/csrf-token')
  return api.post(
    `/api/support/tickets/${ticketId}/resolve`,
    {},
    { headers: { 'X-CSRF-Token': csrf.data.csrf_token } }
  )
}

export async function closeSupportTicket(ticketId) {
  const csrf = await api.get('/api/csrf-token')
  return api.post(
    `/api/support/tickets/${ticketId}/close`,
    {},
    { headers: { 'X-CSRF-Token': csrf.data.csrf_token } }
  )
}

export function fetchSupportTeam() {
  return api.get('/api/support/team')
}

export async function createSupportTeamMember(payload) {
  const csrf = await api.get('/api/csrf-token')
  return api.post('/api/support/team', payload, {
    headers: { 'X-CSRF-Token': csrf.data.csrf_token },
  })
}

export async function updateSupportTeamMember(memberId, payload) {
  const csrf = await api.get('/api/csrf-token')
  return api.put(`/api/support/team/${memberId}`, payload, {
    headers: { 'X-CSRF-Token': csrf.data.csrf_token },
  })
}

export function fetchSupportStats() {
  return api.get('/api/support/stats')
}