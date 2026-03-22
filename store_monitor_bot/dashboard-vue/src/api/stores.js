import api from './axios'

export function fetchStores() {
  return api.get('/api/stores')
}

export async function createStore(payload) {
  const csrf = await api.get('/api/csrf-token')
  return api.post('/api/stores', payload, {
    headers: { 'X-CSRF-Token': csrf.data.csrf_token },
  })
}
