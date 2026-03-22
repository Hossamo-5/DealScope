import { defineStore } from 'pinia'
import { ref } from 'vue'
import { fetchHealth as apiFetch } from '../api/health'

export const useHealthStore = defineStore('health', () => {
  const health = ref(null)
  const loading = ref(false)

  async function load() {
    loading.value = true
    try {
      const { data } = await apiFetch()
      health.value = data
    } finally {
      loading.value = false
    }
  }

  return { health, loading, load }
})
