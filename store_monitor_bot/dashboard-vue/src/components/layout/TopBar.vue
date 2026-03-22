<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { MoonIcon, SunIcon } from '@heroicons/vue/24/outline'
import NotificationBell from './NotificationBell.vue'

defineEmits(['toggle-theme'])
const props = defineProps({
  title: { type: String, required: true },
  systemStatus: { type: String, default: 'unknown' },
  dark: { type: Boolean, default: true },
})

const now = ref(new Date())
let timer

onMounted(() => {
  timer = setInterval(() => {
    now.value = new Date()
  }, 1000)
})
onUnmounted(() => clearInterval(timer))

const statusColor = computed(() => {
  if (props.systemStatus === 'ok') return 'bg-emerald-500'
  if (props.systemStatus === 'degraded') return 'bg-amber-500'
  return 'bg-rose-500'
})
</script>

<template>
  <header class="header sticky top-0 z-20 border-b border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-slate-900/70 backdrop-blur">
    <div class="px-4 md:px-6 py-3 flex items-center justify-between gap-4">
      <div>
        <h1 class="font-bold text-lg">لوحة الإدارة — {{ title }}</h1>
        <p id="current-time" class="text-xs text-slate-500">{{ now.toLocaleString('ar-SA') }}</p>
      </div>

      <div class="flex items-center gap-2">
        <span class="w-2.5 h-2.5 rounded-full" :class="statusColor" />
        <span id="system-status" class="text-xs text-slate-500">{{ props.systemStatus === 'ok' ? '✅ النظام يعمل' : '⚠️ مشاكل' }}</span>
        <button v-tooltip="dark ? 'تفعيل الوضع النهاري' : 'تفعيل الوضع الليلي'" class="rounded-lg border border-slate-300 dark:border-slate-700 p-2" @click="$emit('toggle-theme')">
          <SunIcon v-if="dark" class="w-5 h-5" />
          <MoonIcon v-else class="w-5 h-5" />
        </button>
        <NotificationBell />
        <div class="rounded-full bg-primary-600 text-white w-8 h-8 grid place-items-center">A</div>
      </div>
    </div>
  </header>
</template>
