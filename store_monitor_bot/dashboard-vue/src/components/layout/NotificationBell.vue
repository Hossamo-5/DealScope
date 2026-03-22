<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { BellIcon } from '@heroicons/vue/24/outline'
import { useNotificationsStore } from '../../stores/notifications'
import { timeAgoAr } from '../../utils/format'

const router = useRouter()
const store = useNotificationsStore()
const isOpen = ref(false)
const bellRef = ref(null)

const notifications = computed(() => store.notifications)
const unreadCount = computed(() => store.unreadCount)

function togglePanel() {
  isOpen.value = !isOpen.value
  if (isOpen.value) {
    store.fetchNotifications()
  }
}

async function handleNotifClick(notif) {
  if (!notif.read) {
    await store.markRead(notif.id)
  }
  if (notif.action_url) {
    router.push(notif.action_url)
    isOpen.value = false
  }
}

async function markAllRead() {
  await store.markAllRead()
}

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

function handleOutsideClick(event) {
  if (bellRef.value && !bellRef.value.contains(event.target)) {
    isOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleOutsideClick)
  store.fetchNotifications()
  store.startPolling()
})
onUnmounted(() => {
  document.removeEventListener('click', handleOutsideClick)
  store.stopPolling()
})
</script>

<template>
  <div ref="bellRef" class="relative">
    <button
      v-tooltip="'الإشعارات'"
      class="relative p-2 rounded-lg transition-colors hover:bg-slate-100 dark:hover:bg-slate-700"
      @click="togglePanel"
    >
      <BellIcon class="w-5 h-5 text-slate-600 dark:text-slate-300" />

      <span
        v-if="unreadCount > 0"
        class="absolute -top-1 -right-1 min-w-[18px] h-[18px] bg-red-500 text-white text-xs font-bold rounded-full flex items-center justify-center px-1 animate-pulse"
      >
        {{ unreadCount > 99 ? '99+' : unreadCount }}
      </span>
    </button>

    <Transition
      enter-active-class="transition ease-out duration-200"
      enter-from-class="opacity-0 translate-y-2 scale-95"
      enter-to-class="opacity-100 translate-y-0 scale-100"
      leave-active-class="transition ease-in duration-150"
      leave-from-class="opacity-100 translate-y-0 scale-100"
      leave-to-class="opacity-0 translate-y-2 scale-95"
    >
      <div
        v-if="isOpen"
        class="absolute left-0 top-12 w-96 rounded-xl shadow-2xl border z-50 overflow-hidden bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700"
      >
        <div class="flex items-center justify-between px-4 py-3 border-b border-slate-200 dark:border-slate-700">
          <h3 class="font-semibold text-slate-900 dark:text-white">
            الإشعارات
            <span
              v-if="unreadCount > 0"
              class="mr-2 text-xs bg-blue-100 dark:bg-blue-900 text-blue-600 dark:text-blue-400 px-2 py-0.5 rounded-full"
            >
              {{ unreadCount }} جديد
            </span>
          </h3>
          <button
            v-if="unreadCount > 0"
            class="text-xs text-blue-500 hover:text-blue-600 dark:text-blue-400 dark:hover:text-blue-300"
            @click="markAllRead"
          >
            ✓ قراءة الكل
          </button>
        </div>

        <div class="max-h-96 overflow-y-auto">
          <div v-if="notifications.length === 0" class="flex flex-col items-center py-12 text-center">
            <span class="text-4xl mb-3">🔕</span>
            <p class="text-sm text-slate-500 dark:text-slate-400">لا توجد إشعارات جديدة</p>
          </div>

          <div
            v-for="notif in notifications"
            :key="notif.id"
            class="flex gap-3 px-4 py-3 cursor-pointer transition-colors border-b last:border-0 border-slate-100 dark:border-slate-700/50"
            :class="notif.read
              ? 'hover:bg-slate-50 dark:hover:bg-slate-700/30'
              : 'bg-blue-50/50 dark:bg-blue-900/10 hover:bg-blue-50 dark:hover:bg-blue-900/20'"
            @click="handleNotifClick(notif)"
          >
            <div class="flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center text-xl" :class="iconBg(notif.color)">
              {{ notif.icon }}
            </div>

            <div class="flex-1 min-w-0">
              <div class="flex items-start justify-between gap-2">
                <p
                  class="text-sm font-medium leading-tight"
                  :class="notif.read ? 'text-slate-600 dark:text-slate-300' : 'text-slate-900 dark:text-white'"
                >
                  {{ notif.title }}
                </p>
                <span class="text-xs text-slate-400 dark:text-slate-500 whitespace-nowrap">
                  {{ timeAgoAr(notif.created_at) }}
                </span>
              </div>
              <p class="text-xs text-slate-500 dark:text-slate-400 mt-0.5 break-words">{{ notif.message }}</p>
            </div>

            <div v-if="!notif.read" class="flex-shrink-0 w-2 h-2 rounded-full bg-blue-500 mt-2"></div>
          </div>
        </div>

        <div class="px-4 py-3 border-t border-slate-200 dark:border-slate-700">
          <button
            class="w-full text-sm text-center text-blue-500 hover:text-blue-600 dark:text-blue-400 dark:hover:text-blue-300"
            @click="router.push('/notifications'); isOpen = false"
          >
            عرض كل الإشعارات ←
          </button>
        </div>
      </div>
    </Transition>
  </div>
</template>
