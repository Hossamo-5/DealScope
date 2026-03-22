import api from './axios'

export function fetchLiveDashboard() {
  return api.get('/api/dashboard/live')
}
