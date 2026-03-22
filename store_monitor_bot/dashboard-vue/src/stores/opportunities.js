import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  fetchOpportunities as apiFetch,
  approveOpportunity as apiApprove,
} from '../api/opportunities'

export const useOpportunitiesStore = defineStore('opportunities', () => {
  const items = ref([])
  const total = ref(0)
  const loading = ref(false)
  const currentStatus = ref('new')

  async function load(status = 'new', limit = 20, offset = 0) {
    loading.value = true
    currentStatus.value = status
    try {
      const { data } = await apiFetch(status, limit, offset)
      items.value = data.opportunities || []
      total.value = data.total || 0
    } finally {
      loading.value = false
    }
  }

  async function approve(id, body = {}) {
    await apiApprove(id, body)
    items.value = items.value.filter((o) => o.id !== id)
    total.value = Math.max(0, total.value - 1)
  }

  function reject(id) {
    items.value = items.value.map((o) =>
      o.id === id ? { ...o, status: 'rejected' } : o
    )
  }

  return { items, total, loading, currentStatus, load, approve, reject }
})
