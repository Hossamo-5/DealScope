import api from './axios'

export function fetchStats() {
  return api.get('/api/stats')
}
