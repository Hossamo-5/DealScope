<script setup>
import { computed } from 'vue'
import { formatDateAr, formatNumberAr } from '../../utils/format'

const props = defineProps({ user: { type: Object, required: true } })
defineEmits(['upgrade', 'detail', 'ban', 'open'])

const planMap = {
  free: {
    label: '🆓 مجاني',
    tooltip: 'خطة مجانية - 3 منتجات، فحص كل 60 دقيقة',
    cls: 'bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200',
  },
  basic: {
    label: '⭐ أساسي',
    tooltip: 'خطة أساسية - 50 منتج، فحص كل 30 دقيقة',
    cls: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
  },
  professional: {
    label: '💎 احترافي',
    tooltip: 'خطة احترافية - 300 منتج، فحص كل 15 دقيقة',
    cls: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
  },
}

const planColor = (plan) => ({
  free: '#64748b',
  basic: '#2563eb',
  professional: '#d97706',
}[plan] || '#64748b')

const userDisplayName = computed(() => {
  const first = props.user.first_name || ''
  const last = props.user.last_name || ''
  const full = `${first} ${last}`.trim()
  return full || props.user.username || 'مستخدم'
})

const avatarInitial = computed(() => {
  const first = props.user.first_name?.[0]
  const username = props.user.username?.[0]
  return (first || username || '?').toUpperCase()
})

const expiryCls = computed(() => {
  if (!props.user.plan_expires_at) return 'text-slate-500'
  return new Date(props.user.plan_expires_at) < new Date() ? 'text-rose-500' : 'text-emerald-500'
})

const onlineState = computed(() => {
  if (!props.user.last_active) return 'offline'
  const diffMs = Date.now() - new Date(props.user.last_active).getTime()
  if (diffMs < 5 * 60 * 1000) return 'online'
  if (diffMs < 60 * 60 * 1000) return 'recent'
  return 'offline'
})

const sparklinePath = computed(() => {
  const values = props.user.daily_activity || [0, 0, 0, 0, 0, 0, 0]
  const max = Math.max(...values, 1)
  const points = values.map((v, i) => {
    const x = i * (50 / (values.length - 1 || 1))
    const y = 16 - (Number(v) / max) * 14
    return `${x},${y}`
  })
  return points.join(' ')
})

const activityTooltip = computed(() => {
  if (onlineState.value === 'online') return 'نشط الآن (آخر 5 دقائق)'
  if (onlineState.value === 'recent') return 'نشط منذ أقل من ساعة'
  return 'غير متصل'
})

const activityEmoji = computed(() => {
  if (onlineState.value === 'online') return '🟢'
  if (onlineState.value === 'recent') return '🟡'
  return '⚫'
})
</script>

<template>
  <tr class="border-b border-slate-200 dark:border-slate-800 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/40" @click="$emit('open', user)">
    <td class="py-2 px-2">
      <div class="flex items-center gap-3">
        <div class="w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold text-white" :style="{ background: planColor(user.plan) }">
          {{ avatarInitial }}
        </div>
        <div class="flex flex-col">
          <span class="font-medium text-sm text-slate-900 dark:text-slate-100">{{ userDisplayName }}</span>
          <span class="text-xs text-slate-500 dark:text-slate-400">@{{ user.username || 'بدون يوزرنيم' }}</span>
          <span class="text-xs text-blue-500 dark:text-blue-400 font-mono">ID: {{ user.telegram_id || '—' }}</span>
        </div>
      </div>
    </td>
    <td class="py-2 px-2 text-xs font-mono text-blue-500 dark:text-blue-400">{{ user.telegram_id || '—' }}</td>
    <td class="py-2 px-2">
      <span v-tooltip="planMap[user.plan]?.tooltip" class="text-xs rounded-full px-2 py-1" :class="planMap[user.plan]?.cls">{{ planMap[user.plan]?.label || user.plan }}</span>
    </td>
    <td class="py-2 px-2" :class="expiryCls">{{ formatDateAr(user.plan_expires_at) }}</td>
    <td class="py-2 px-2">{{ formatNumberAr(user.products_count) }}</td>
    <td class="py-2 px-2">{{ formatDateAr(user.created_at) }}</td>
    <td class="py-2 px-2">
      <div class="flex items-center gap-2">
        <span v-tooltip="activityTooltip">{{ activityEmoji }}</span>
        <span class="w-2.5 h-2.5 rounded-full" :class="onlineState === 'online' ? 'bg-emerald-500' : (onlineState === 'recent' ? 'bg-amber-500' : 'bg-slate-500')" />
        <svg width="50" height="16" viewBox="0 0 50 16" class="opacity-80">
          <polyline :points="sparklinePath" fill="none" stroke="currentColor" stroke-width="1.5" />
        </svg>
      </div>
    </td>
    <td class="py-2 px-2 space-x-2 space-x-reverse" @click.stop>
      <button v-tooltip="'ترقية أو تغيير خطة الاشتراك'" class="rounded bg-primary-600 text-white px-2 py-1 text-xs" @click="$emit('upgrade', user)">⬆️</button>
      <button v-tooltip="'عرض البروفايل الكامل للمستخدم'" class="rounded bg-slate-600 text-white px-2 py-1 text-xs" @click="$emit('detail', user)">👁</button>
      <button v-tooltip="user.is_banned ? 'رفع الحظر عن المستخدم' : 'حظر المستخدم'" class="rounded px-2 py-1 text-xs text-white" :class="user.is_banned ? 'bg-emerald-600' : 'bg-rose-600'" @click="$emit('ban', user)">{{ user.is_banned ? '✅' : '🚫' }}</button>
    </td>
  </tr>
</template>
