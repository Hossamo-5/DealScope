<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/auth'
import { fetchLiveDashboard } from '../../api/live'

const router = useRouter()
const auth = useAuthStore()

const activities = ref([])
const activeNow = ref(0)
const paused = ref(false)
const wsConnected = ref(false)
let ws = null
let pollInterval = null

const actionColor = (action) => {
  if (action?.includes('product')) return 'text-red-500'
  if (action?.includes('deal')) return 'text-yellow-500'
  if (action?.includes('alert')) return 'text-emerald-500'
  if (action?.includes('subscription') || action?.includes('upgrade')) return 'text-blue-500'
  return 'text-slate-400'
}

const openProfile = (item) => {
  router.push(`/users/${item.user.id}`)
}

const addActivity = (item) => {
  if (paused.value) return
  activities.value = [item, ...activities.value].slice(0, 10)
}

const pollFallback = async () => {
  try {
    const { data } = await fetchLiveDashboard()
    activeNow.value = data.active_now || 0
    activities.value = (data.recent_activities || []).slice(0, 10)
  } catch (_err) {
    // ignore transient polling failures
  }
}

const startPolling = () => {
  if (pollInterval) return
  pollFallback()
  pollInterval = setInterval(pollFallback, 5000)
}

const stopPolling = () => {
  if (pollInterval) clearInterval(pollInterval)
  pollInterval = null
}

const connect = () => {
  const token = auth.token
  if (!token) {
    startPolling()
    return
  }
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const url = `${protocol}://${window.location.host}/ws/activity?token=${encodeURIComponent(token)}`

  ws = new WebSocket(url)
  ws.onopen = () => {
    wsConnected.value = true
    stopPolling()
  }
  ws.onmessage = (ev) => {
    try {
      const payload = JSON.parse(ev.data)
      if (payload?.type === 'user_action') {
        addActivity(payload)
      }
    } catch (_err) {
      // ignore malformed events
    }
  }
  ws.onclose = () => {
    wsConnected.value = false
    startPolling()
  }
  ws.onerror = () => {
    wsConnected.value = false
    startPolling()
  }
}

onMounted(() => {
  connect()
})

onUnmounted(() => {
  if (ws) ws.close()
  stopPolling()
})
</script>

<template>
  <div class="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-4 h-full">
    <div class="flex items-center justify-between mb-3">
      <h3 class="font-semibold">النشاط المباشر</h3>
      <div class="flex items-center gap-2 text-xs text-slate-500">
        <span class="w-2 h-2 rounded-full" :class="wsConnected ? 'bg-emerald-500' : 'bg-amber-500'" />
        <span>{{ activeNow }} متصل</span>
      </div>
    </div>

    <div class="flex items-center justify-between mb-2">
      <span class="text-xs text-slate-500">⚡ الآن</span>
      <button class="text-xs rounded border border-slate-300 dark:border-slate-700 px-2 py-1" @click="paused = !paused">{{ paused ? 'استئناف' : 'إيقاف مؤقت' }}</button>
    </div>

    <div class="space-y-2 max-h-80 overflow-auto">
      <button
        v-for="(item, idx) in activities"
        :key="idx"
        class="w-full text-right rounded-lg border border-slate-200 dark:border-slate-800 p-2 hover:bg-slate-50 dark:hover:bg-slate-800 transition"
        @click="openProfile(item)"
      >
        <div class="text-sm font-medium">
          <span :class="actionColor(item.action)">●</span>
          @{{ item.user?.username || item.user?.name || item.user?.id }}
          <span class="text-slate-400">← {{ item.action }}</span>
        </div>
        <div class="text-xs text-slate-500 truncate">{{ item.details?.product || item.details?.product_name || item.details?.text || '—' }}</div>
      </button>
    </div>

    <router-link class="block mt-3 text-xs text-primary-600" to="/users">عرض كل الأنشطة</router-link>
  </div>
</template>
