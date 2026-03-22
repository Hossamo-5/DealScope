import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import api from '../api/axios'

export const useNotificationsStore = defineStore('notifications', () => {
  const notifications = ref([])
  const unreadCount = computed(() => notifications.value.filter((n) => !n.read).length)
  let pollInterval = null

  async function fetchNotifications() {
    const { data } = await api.get('/api/notifications')
    notifications.value = data.notifications || []
  }

  async function markRead(id) {
    await api.post(`/api/notifications/${id}/read`)
    const item = notifications.value.find((n) => n.id === id)
    if (item) item.read = true
  }

  async function markAllRead() {
    await api.post('/api/notifications/read-all')
    notifications.value = notifications.value.map((n) => ({ ...n, read: true }))
  }

  function startPolling() {
    if (pollInterval) return
    pollInterval = setInterval(fetchNotifications, 30000)
  }

  function stopPolling() {
    if (pollInterval) {
      clearInterval(pollInterval)
      pollInterval = null
    }
  }

  return {
    notifications,
    unreadCount,
    fetchNotifications,
    markRead,
    markAllRead,
    startPolling,
    stopPolling,
  }
})
