<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useToast } from 'vue-toastification'

import Sidebar from '../../components/layout/Sidebar.vue'
import TopBar from '../../components/layout/TopBar.vue'
import PageHeader from '../../components/layout/PageHeader.vue'

import { useAuthStore } from '../../stores/auth'
import { useStatsStore } from '../../stores/stats'
import { useHealthStore } from '../../stores/health'

const auth = useAuthStore()
const statsStore = useStatsStore()
const healthStore = useHealthStore()
const router = useRouter()
const route = useRoute()
const toast = useToast()

const collapsed = ref(false)
const dark = ref(localStorage.getItem('sm_dark') !== '0')

const pageTitle = computed(() => {
  const map = {
    home: 'الرئيسية',
    opportunities: 'الفرص',
    users: 'المستخدمون',
    'user-profile': 'بروفايل المستخدم',
    support: 'الدعم الفني',
    'support-team': 'فريق الدعم',
    stores: 'المتاجر',
    'store-requests': 'طلبات المتاجر',
    notifications: 'الإشعارات',
    settings: 'الإعدادات',
    health: 'صحة النظام',
  }
  return map[route.name] || 'لوحة الإدارة'
})

const systemStatus = computed(() => healthStore.health?.status || 'unknown')

const toggleTheme = () => {
  dark.value = !dark.value
  localStorage.setItem('sm_dark', dark.value ? '1' : '0')
  document.documentElement.classList.toggle('dark', dark.value)
}

const logout = async () => {
  await auth.logout()
  toast.success('تم تسجيل الخروج')
  router.push('/login')
}

onMounted(async () => {
  document.documentElement.classList.toggle('dark', dark.value)
  await Promise.all([statsStore.load(), healthStore.load()])
})
</script>

<template>
  <div id="app-section" class="min-h-screen bg-slate-100 dark:bg-slate-950 text-slate-900 dark:text-slate-100 flex">
    <Sidebar
      :collapsed="collapsed"
      :new-opportunities="statsStore.stats.new_opportunities"
      :open-support-tickets="statsStore.stats.open_support_tickets || 0"
      :pending-store-requests="statsStore.stats.pending_store_requests || 0"
      @toggle="collapsed = !collapsed"
      @logout="logout"
    />

    <main class="flex-1 min-w-0">
      <TopBar :title="pageTitle" :system-status="systemStatus" :dark="dark" @toggle-theme="toggleTheme" />
      <div class="p-4 md:p-6">
        <PageHeader :title="pageTitle" />
        <transition name="fade" mode="out-in">
          <router-view />
        </transition>
      </div>
    </main>
  </div>
</template>
