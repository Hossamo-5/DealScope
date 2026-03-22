<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useToast } from 'vue-toastification'

import { useStatsStore } from '../../stores/stats'
import { useOpportunitiesStore } from '../../stores/opportunities'
import { fetchLiveDashboard } from '../../api/live'

import StatsGrid from '../../components/dashboard/StatsGrid.vue'
import OpportunitiesTable from '../../components/dashboard/OpportunitiesTable.vue'
import QuickActions from '../../components/dashboard/QuickActions.vue'
import LiveActivityFeed from '../../components/dashboard/LiveActivityFeed.vue'
import ApproveModal from '../../components/opportunities/ApproveModal.vue'

const statsStore = useStatsStore()
const opportunitiesStore = useOpportunitiesStore()
const toast = useToast()
const router = useRouter()

const approving = ref(false)
const approveOpen = ref(false)
const selected = ref(null)
const live = ref({ top_users_today: [], recent_alerts: [] })
let intervalId
let liveIntervalId

const openApprove = (item) => {
  selected.value = item
  approveOpen.value = true
}

const onApprove = async (payload) => {
  if (!selected.value) return
  approving.value = true
  try {
    await opportunitiesStore.approve(selected.value.id, payload)
    toast.success('تم اعتماد الفرصة')
    approveOpen.value = false
  } catch (_err) {
    toast.error('فشل اعتماد الفرصة')
  } finally {
    approving.value = false
  }
}

const onReject = (item) => {
  opportunitiesStore.reject(item.id)
  toast.info('تم تحديث الحالة محلياً إلى مرفوضة')
}

const reviewStoreRequests = () => {
  router.push('/store-requests')
}

const loadLiveWidgets = async () => {
  try {
    const { data } = await fetchLiveDashboard()
    live.value = data || { top_users_today: [], recent_alerts: [] }
  } catch (_err) {
    // ignore transient issues
  }
}

onMounted(async () => {
  await Promise.all([statsStore.load(), opportunitiesStore.load('new'), loadLiveWidgets()])
  intervalId = setInterval(() => statsStore.load(), 30000)
  liveIntervalId = setInterval(loadLiveWidgets, 30000)
})
onUnmounted(() => {
  clearInterval(intervalId)
  clearInterval(liveIntervalId)
})
</script>

<template>
  <div id="section-dashboard" class="space-y-4">
    <StatsGrid :stats="statsStore.stats" :loading="statsStore.loading" />

    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div class="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-4">
        <p class="text-sm text-slate-500"><span v-tooltip="'نشط الآن (آخر 5 دقائق)'">🟢</span> متصل الآن</p>
        <p class="text-2xl font-bold">{{ statsStore.stats.active_now || 0 }}</p>
      </div>
      <div class="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-4">
        <p class="text-sm text-slate-500">📈 جديد اليوم</p>
        <p class="text-2xl font-bold">{{ statsStore.stats.new_today || 0 }}</p>
      </div>
    </div>

    <div class="grid grid-cols-1 xl:grid-cols-4 gap-4">
      <div class="xl:col-span-2">
        <div class="flex justify-end mb-2">
          <button v-tooltip="'تحديث قائمة الفرص الجديدة'" class="refresh-btn text-xs rounded border border-slate-300 dark:border-slate-700 px-3 py-1" @click="opportunitiesStore.load('new')">تحديث</button>
        </div>
        <OpportunitiesTable :items="opportunitiesStore.items" :loading="opportunitiesStore.loading" @approve="openApprove" @reject="onReject" />
      </div>
      <div class="space-y-4">
        <QuickActions :subscribers-count="statsStore.stats.users_count || 0" @review-requests="reviewStoreRequests" />
        <div class="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-4">
          <h3 class="font-semibold mb-2">أكثر المستخدمين نشاطاً اليوم</h3>
          <ol class="text-sm space-y-1">
            <li v-for="u in live.top_users_today || []" :key="u.telegram_id">
              @{{ u.username || u.first_name || u.telegram_id }} — {{ u.actions }} فعل
            </li>
            <li v-if="!(live.top_users_today || []).length" class="text-slate-500">لا توجد بيانات</li>
          </ol>
        </div>
        <div class="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-4">
          <h3 class="font-semibold mb-2">آخر التنبيهات المرسلة</h3>
          <ul class="text-sm space-y-1">
            <li v-for="(a, idx) in live.recent_alerts || []" :key="idx">
              {{ a.product || 'منتج' }} — {{ a.user || 'مستخدم' }} — {{ a.alert_type }}
            </li>
            <li v-if="!(live.recent_alerts || []).length" class="text-slate-500">لا توجد تنبيهات</li>
          </ul>
        </div>
      </div>
      <div>
        <LiveActivityFeed />
      </div>
    </div>

    <ApproveModal v-model="approveOpen" :opportunity="selected" :loading="approving" @confirm="onApprove" />
  </div>
</template>
