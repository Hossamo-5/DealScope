import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  fetchUsers as apiFetchUsers,
  fetchUserDetail as apiFetchDetail,
  fetchUserProfile as apiFetchProfile,
  fetchUserActivity as apiFetchActivity,
  upgradeUser as apiUpgrade,
  toggleBanUser as apiToggleBan,
  sendMessageToUser as apiSendMessage,
} from '../api/users'

export const useUsersStore = defineStore('users', () => {
  const users = ref([])
  const total = ref(0)
  const page = ref(1)
  const loading = ref(false)
  const detail = ref(null)
  const detailLoading = ref(false)

  const profileCache = ref({})
  const activityCache = ref({})

  async function load(params = {}) {
    loading.value = true
    try {
      const { data } = await apiFetchUsers({ page: page.value, limit: 20, ...params })
      users.value = data.users || []
      total.value = data.total || 0
    } finally {
      loading.value = false
    }
  }

  async function loadDetail(telegramId) {
    detailLoading.value = true
    try {
      const { data } = await apiFetchDetail(telegramId)
      detail.value = data
    } finally {
      detailLoading.value = false
    }
  }

  async function loadProfile(telegramId, force = false) {
    const key = String(telegramId)
    const cached = profileCache.value[key]
    const now = Date.now()
    if (!force && cached && now - cached.fetchedAt < 60000) {
      return cached.data
    }

    const { data } = await apiFetchProfile(telegramId)
    profileCache.value[key] = { data, fetchedAt: now }
    return data
  }

  async function loadActivity(telegramId, params = {}, force = false) {
    const cacheKey = `${telegramId}:${JSON.stringify(params)}`
    const cached = activityCache.value[cacheKey]
    const now = Date.now()
    if (!force && cached && now - cached.fetchedAt < 60000) {
      return cached.data
    }

    const { data } = await apiFetchActivity(telegramId, params)
    activityCache.value[cacheKey] = { data, fetchedAt: now }
    return data
  }

  async function upgrade(telegramId, plan, days) {
    const { data } = await apiUpgrade(telegramId, plan, days)
    // optimistic update
    const idx = users.value.findIndex((u) => u.telegram_id === telegramId)
    if (idx >= 0) {
      users.value[idx].plan = plan
      users.value[idx].plan_expires_at = data.user?.plan_expires_at || null
    }
    profileCache.value[String(telegramId)] = undefined
    return data
  }

  async function toggleBan(telegramId, isBanned = false) {
    const { data } = await apiToggleBan(telegramId, isBanned)
    const idx = users.value.findIndex((u) => u.telegram_id === telegramId)
    if (idx >= 0) {
      users.value[idx].is_banned = Boolean(data.user?.is_banned)
    }
    profileCache.value[String(telegramId)] = undefined
    return data
  }

  async function sendDirectMessage(telegramId, message) {
    const { data } = await apiSendMessage(telegramId, message)
    return data
  }

  return {
    users,
    total,
    page,
    loading,
    detail,
    detailLoading,
    profileCache,
    activityCache,
    load,
    loadDetail,
    loadProfile,
    loadActivity,
    upgrade,
    toggleBan,
    sendDirectMessage,
  }
})
