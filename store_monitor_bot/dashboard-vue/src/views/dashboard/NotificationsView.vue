<script setup>
import { computed, onMounted } from 'vue'
import { useNotificationsStore } from '../../stores/notifications'
import { timeAgoAr } from '../../utils/format'

const store = useNotificationsStore()

const notifications = computed(() => store.notifications)
const unreadCount = computed(() => store.unreadCount)

function iconBg(color) {
  const map = {
    blue: 'bg-blue-100 dark:bg-blue-900/30',
    orange: 'bg-orange-100 dark:bg-orange-900/30',
    green: 'bg-green-100 dark:bg-green-900/30',
    red: 'bg-red-100 dark:bg-red-900/30',
    purple: 'bg-purple-100 dark:bg-purple-900/30',
  }
  return map[color] || map.blue
}

async function markRead(item) {
  if (!item.read) {
    await store.markRead(item.id)
  }
}

onMounted(() => {
  store.fetchNotifications()
})
</script>

<template>
  <div class="space-y-4">
    <div class="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-4 flex items-center justify-between">
      <h3 class="font-semibold">كل الإشعارات</h3>
      <button
        v-if="unreadCount > 0"
        class="text-sm text-blue-500 hover:text-blue-600 dark:text-blue-400 dark:hover:text-blue-300"
        @click="store.markAllRead"
      >
        ✓ قراءة الكل
      </button>
    </div>

    <div class="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 overflow-hidden">
      <div v-if="!notifications.length" class="py-12 text-center text-slate-500 dark:text-slate-400">لا توجد إشعارات</div>
      <div
        v-for="item in notifications"
        :key="item.id"
        class="flex gap-3 px-4 py-3 border-b border-slate-100 dark:border-slate-800 last:border-0"
        :class="item.read ? '' : 'bg-blue-50/50 dark:bg-blue-900/10'"
        @click="markRead(item)"
      >
        <div class="flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center text-xl" :class="iconBg(item.color)">
          {{ item.icon }}
        </div>
        <div class="flex-1 min-w-0">
          <div class="flex items-center justify-between gap-2">
            <p class="font-medium text-sm">{{ item.title }}</p>
            <span class="text-xs text-slate-400">{{ timeAgoAr(item.created_at) }}</span>
          </div>
          <p class="text-xs text-slate-500 dark:text-slate-400 break-words">{{ item.message }}</p>
        </div>
      </div>
    </div>
  </div>
</template>
