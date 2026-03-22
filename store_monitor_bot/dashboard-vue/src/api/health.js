import api from './axios'

export function fetchHealth() {
  return api.get('/api/health')
}

export function fetchStores() {
  return api.get('/api/stores')
}
