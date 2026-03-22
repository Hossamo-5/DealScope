import { defineStore } from 'pinia'
import { ref } from 'vue'
import { fetchStats as apiFetchStats } from '../api/stats'

export const useStatsStore = defineStore('stats', () => {
  const stats = ref({
    users_count: 0,
    free_count: 0,
    basic_count: 0,
    professional_count: 0,
    banned_count: 0,
    products_count: 0,
    new_opportunities: 0,
    sent_today: 0,
    pending_store_requests: 0,
  })
  const loading = ref(false)

  async function load() {
    loading.value = true
    try {
      const { data } = await apiFetchStats()
      stats.value = data
    } finally {
      loading.value = false
    }
  }

  return { stats, loading, load }
})
