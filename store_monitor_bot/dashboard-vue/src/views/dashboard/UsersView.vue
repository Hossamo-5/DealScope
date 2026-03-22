<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useToast } from 'vue-toastification'
import { useUsersStore } from '../../stores/users'
import { useStatsStore } from '../../stores/stats'
import UsersTable from '../../components/users/UsersTable.vue'
import UpgradeModal from '../../components/users/UpgradeModal.vue'
import UserDetailModal from '../../components/users/UserDetailModal.vue'
import BaseSelect from '../../components/ui/BaseSelect.vue'

const usersStore = useUsersStore()
const statsStore = useStatsStore()
const toast = useToast()
const router = useRouter()

const search = ref('')
const plan = ref('')
const sortBy = ref('created_at')
const selectedUser = ref(null)
const upgradeOpen = ref(false)
const detailOpen = ref(false)
const upgrading = ref(false)
let debounceId

const planOptions = [
  { value: '', label: 'كل الخطط' },
  { value: 'free', label: '🆓 مجاني' },
  { value: 'basic', label: '⭐ أساسي' },
  { value: 'professional', label: '💎 احترافي' },
]

const sortOptions = [
  { value: 'created_at', label: 'تاريخ التسجيل' },
  { value: 'products', label: 'المنتجات' },
  { value: 'plan', label: 'الخطة' },
]

const load = async () => {
  await Promise.all([
    usersStore.load({ search: search.value, plan: plan.value || undefined }),
    statsStore.load(),
  ])
}

watch(search, () => {
  clearTimeout(debounceId)
  debounceId = setTimeout(load, 300)
})

watch([plan, sortBy], load)

const sortedUsers = computed(() => {
  const arr = [...usersStore.users]
  if (sortBy.value === 'products') return arr.sort((a, b) => (b.products_count || 0) - (a.products_count || 0))
  if (sortBy.value === 'plan') return arr.sort((a, b) => (a.plan || '').localeCompare(b.plan || ''))
  return arr.sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0))
})

const openUpgrade = (u) => {
  selectedUser.value = u
  upgradeOpen.value = true
}

const openDetail = async (u) => {
  selectedUser.value = u
  detailOpen.value = true
  await usersStore.loadDetail(u.telegram_id)
}

const openProfile = (u) => {
  router.push(`/users/${u.telegram_id}`)
}

const confirmUpgrade = async ({ plan, days }) => {
  if (!selectedUser.value) return
  upgrading.value = true
  try {
    await usersStore.upgrade(selectedUser.value.telegram_id, plan, days)
    toast.success(`تم ترقية @${selectedUser.value.username || selectedUser.value.telegram_id}`)
    upgradeOpen.value = false
    await load()
  } catch (_err) {
    toast.error('تعذر ترقية المستخدم')
  } finally {
    upgrading.value = false
  }
}

const toggleBan = async (u) => {
  if (!confirm('هل تريد تنفيذ العملية؟')) return
  try {
    const res = await usersStore.toggleBan(u.telegram_id, u.is_banned)
    toast.success(res.user?.is_banned ? 'تم الحظر' : 'تم رفع الحظر')
  } catch (_err) {
    toast.error('تعذر تنفيذ العملية')
  }
}

onMounted(load)
</script>

<template>
  <div id="section-users" class="space-y-4">
    <div class="grid grid-cols-2 md:grid-cols-5 gap-3">
      <div class="rounded-xl p-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">الكل: {{ statsStore.stats.users_count }}</div>
      <div class="rounded-xl p-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">مجاني: {{ statsStore.stats.free_count }}</div>
      <div class="rounded-xl p-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">أساسي: {{ statsStore.stats.basic_count }}</div>
      <div class="rounded-xl p-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">احترافي: {{ statsStore.stats.professional_count }}</div>
      <div class="rounded-xl p-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">محظور: {{ statsStore.stats.banned_count }}</div>
    </div>

    <div class="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-4 grid grid-cols-1 md:grid-cols-3 gap-3">
      <input v-model="search" class="rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-3 py-2" placeholder="بحث باسم المستخدم أو Telegram ID" />
      <BaseSelect v-model="plan" :options="planOptions" />
      <BaseSelect v-model="sortBy" :options="sortOptions" />
    </div>

    <UsersTable
      :users="sortedUsers"
      :loading="usersStore.loading"
      @upgrade="openUpgrade"
      @detail="openProfile"
      @ban="toggleBan"
      @open="openProfile"
    />

    <UpgradeModal v-model="upgradeOpen" :user="selectedUser" :loading="upgrading" @confirm="confirmUpgrade" />
    <UserDetailModal v-model="detailOpen" :detail="usersStore.detail" :loading="usersStore.detailLoading" />
  </div>
</template>
