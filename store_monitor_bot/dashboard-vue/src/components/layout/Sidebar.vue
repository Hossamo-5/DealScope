<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Cog6ToothIcon, ArrowRightOnRectangleIcon } from '@heroicons/vue/24/outline'

const props = defineProps({
  collapsed: { type: Boolean, default: false },
  newOpportunities: { type: Number, default: 0 },
  openSupportTickets: { type: Number, default: 0 },
  pendingStoreRequests: { type: Number, default: 0 },
})

const route = useRoute()
const emit = defineEmits(['toggle', 'logout'])

const navItems = computed(() => [
  { to: '/', name: 'home', label: 'الرئيسية', icon: '📊' },
  { to: '/opportunities', name: 'opportunities', label: 'الفرص', icon: '💡', badge: props.newOpportunities },
  { to: '/users', name: 'users', label: 'المستخدمون', icon: '👥' },
  { to: '/support', name: 'support', label: 'الدعم الفني', icon: '🎧', badge: props.openSupportTickets },
  { to: '/support/team', name: 'support-team', label: 'فريق الدعم', icon: '🧑‍💼' },
  { to: '/stores', name: 'stores', label: 'المتاجر', icon: '🏪' },
  { to: '/store-requests', name: 'store-requests', label: 'طلبات المتاجر', icon: '📋', badge: props.pendingStoreRequests },
  { to: '/menu-builder', name: 'menu-builder', label: 'منشئ القائمة', icon: '🎛' },
  { to: '/id-resolver', name: 'id-resolver', label: 'محلل المعرفات', icon: '🔍' },
  { to: '/groups', name: 'groups', label: 'المجموعات', icon: '👥' },
  { to: '/bots', name: 'bots', label: 'البوتات', icon: '🤖' },
  { to: '/health', name: 'health', label: 'صحة النظام', icon: '💊' },
])

const handleLogout = () => {
  emit('logout')
}
</script>

<template>
  <aside class="hidden md:flex flex-col h-full border-l border-slate-200 dark:border-slate-800 bg-white/90 dark:bg-slate-900/80 backdrop-blur sidebar-transition" :class="collapsed ? 'w-20' : 'w-72'">
    <div class="p-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
      <h2 class="font-bold" v-if="!collapsed">🛍 Store Monitor</h2>
      <button v-tooltip="'طي القائمة الجانبية'" class="px-2 py-1 rounded bg-slate-200 dark:bg-slate-800" @click="$emit('toggle')">☰</button>
    </div>

    <nav class="p-3 flex-1 space-y-1">
      <router-link v-for="item in navItems" :key="item.name" :to="item.to" class="flex items-center gap-3 rounded-xl px-3 py-2 transition" :class="[(item.name !== 'store-requests' ? 'nav-btn' : ''), route.name === item.name ? 'active bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300' : 'hover:bg-slate-100 dark:hover:bg-slate-800']">
        <span v-tooltip="item.label">{{ item.icon }}</span>
        <span v-if="!collapsed" class="flex-1">{{ item.label }}</span>
        <span v-if="!collapsed && item.badge" class="text-xs bg-primary-600 text-white rounded-full px-2">{{ item.badge }}</span>
      </router-link>
    </nav>

    <div class="flex-1"></div>

    <div class="p-3 border-t border-slate-700 dark:border-slate-700 pt-3 mt-3 space-y-1">
      <RouterLink
        to="/settings"
        class="flex items-center gap-3 px-3 py-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-700 transition-colors"
      >
        <Cog6ToothIcon class="w-5 h-5" />
        <span v-if="!collapsed">الإعدادات</span>
      </RouterLink>

      <button
        v-tooltip="'تسجيل الخروج من لوحة الإدارة'"
        class="w-full flex items-center gap-3 px-3 py-2 rounded-lg transition-colors text-red-400 hover:text-red-300 hover:bg-red-900/20"
        @click="handleLogout"
      >
        <ArrowRightOnRectangleIcon class="w-5 h-5" />
        <span v-if="!collapsed">تسجيل الخروج</span>
      </button>
    </div>
  </aside>
</template>
