<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useToast } from 'vue-toastification'
import { useUsersStore } from '../../stores/users'
import { formatDateAr, formatDateTimeAr } from '../../utils/format'
import UpgradeModal from '../../components/users/UpgradeModal.vue'
import BaseModal from '../../components/ui/BaseModal.vue'

const route = useRoute()
const router = useRouter()
const usersStore = useUsersStore()
const toast = useToast()

const loading = ref(false)
const profile = ref(null)
const activityLog = ref([])
const activeTab = ref('stats')
const upgradeOpen = ref(false)
const upgrading = ref(false)
const banConfirmOpen = ref(false)
const banning = ref(false)
const messageOpen = ref(false)
const sending = ref(false)
const messageText = ref('')

const telegramId = computed(() => Number(route.params.telegram_id))
const userLabel = computed(() => profile.value?.user?.username || profile.value?.user?.telegram_id || '')
const banButtonLabel = computed(() => (profile.value?.user?.is_banned ? '✅ رفع الحظر' : '🚫 حظر'))
const messageLength = computed(() => (messageText.value || '').length)
const messagePreview = computed(() => messageText.value || '[نص الرسالة]')

const quickTemplates = [
  { label: 'مرحباً 👋', text: 'مرحباً! كيف يمكننا مساعدتك؟' },
  { label: 'تم تفعيل اشتراكك ✅', text: 'تم تفعيل اشتراكك بنجاح! يمكنك الآن الاستمتاع بجميع الميزات.' },
  { label: 'تم الحظر 🚫', text: 'تم تعليق حسابك بسبب مخالفة شروط الاستخدام.' },
  { label: 'تنبيه مهم ⚠️', text: 'لديك تنبيه مهم يحتاج انتباهك. يرجى التواصل مع الدعم.' },
]

const loadProfile = async () => {
  loading.value = true
  try {
    profile.value = await usersStore.loadProfile(telegramId.value)
  } finally {
    loading.value = false
  }
}

const loadActivities = async () => {
  const data = await usersStore.loadActivity(telegramId.value, { page: 1, limit: 50, action: 'all' })
  activityLog.value = data.activities || []
}

watch(activeTab, async (tab) => {
  if (tab === 'activity' && !activityLog.value.length) {
    await loadActivities()
  }
})

onMounted(loadProfile)

const onUpgrade = async ({ plan, days }) => {
  if (!profile.value?.user) return
  upgrading.value = true
  const currentUser = profile.value.user
  try {
    const response = await usersStore.upgrade(currentUser.telegram_id, plan, days)
    profile.value.user.plan = response.user?.plan || plan
    profile.value.user.plan_expires_at = response.user?.plan_expires_at || profile.value.user.plan_expires_at
    await loadProfile()
    toast.success(`✅ تم ترقية @${currentUser.username || currentUser.telegram_id}`)
    upgradeOpen.value = false
  } catch (_err) {
    toast.error('تعذر ترقية المستخدم')
  } finally {
    upgrading.value = false
  }
}

const confirmBanAction = async () => {
  if (!profile.value?.user) return
  banning.value = true
  const user = profile.value.user
  try {
    const response = await usersStore.toggleBan(user.telegram_id, user.is_banned)
    const banned = Boolean(response.user?.is_banned)
    profile.value.user.is_banned = banned
    banConfirmOpen.value = false
    await loadProfile()
    toast.success(banned ? `🚫 تم حظر @${user.username || user.telegram_id}` : `✅ تم رفع الحظر عن @${user.username || user.telegram_id}`)
  } catch (_err) {
    toast.error('تعذر تنفيذ العملية')
  } finally {
    banning.value = false
  }
}

const applyTemplate = (text) => {
  messageText.value = text
}

const sendDirectMessage = async () => {
  if (!profile.value?.user) return
  const text = (messageText.value || '').trim()
  if (!text) {
    toast.error('اكتب رسالة أولاً')
    return
  }
  sending.value = true
  const user = profile.value.user
  try {
    await usersStore.sendDirectMessage(user.telegram_id, text)
    messageOpen.value = false
    messageText.value = ''
    toast.success(`✅ تم إرسال الرسالة لـ @${user.username || user.telegram_id}`)
  } catch (_err) {
    toast.error('تعذر إرسال الرسالة')
  } finally {
    sending.value = false
  }
}
</script>

<template>
  <div class="space-y-4">
    <button v-tooltip="'العودة إلى قائمة المستخدمين'" class="text-sm text-primary-600" @click="router.push('/users')">← رجوع</button>

    <div class="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-4" v-if="!loading && profile">
      <div class="flex items-center justify-between gap-3">
        <div>
          <h3 class="font-bold text-lg">@{{ profile.user.username || profile.user.telegram_id }}</h3>
          <p class="text-sm text-slate-500">{{ profile.user.first_name || '—' }} — ID: {{ profile.user.telegram_id }}</p>
          <p class="text-sm text-slate-500">{{ profile.user.plan }} | فعّال حتى {{ formatDateAr(profile.user.plan_expires_at) }}</p>
          <p class="text-xs text-slate-400">آخر نشاط: {{ formatDateTimeAr(profile.user.last_active) }}</p>
        </div>
        <div class="flex gap-2">
          <button v-tooltip="'ترقية الاشتراك'" class="px-3 py-1.5 rounded bg-primary-600 text-white text-sm" @click="upgradeOpen = true">⬆️ ترقية</button>
          <button v-tooltip="'إرسال رسالة مباشرة عبر تيليغرام'" class="px-3 py-1.5 rounded bg-sky-600 text-white text-sm" @click="messageOpen = true">📨 رسالة</button>
          <button v-tooltip="profile.user.is_banned ? 'رفع الحظر عن المستخدم' : 'حظر المستخدم من استخدام البوت'" class="px-3 py-1.5 rounded text-white text-sm" :class="profile.user.is_banned ? 'bg-emerald-600' : 'bg-rose-600'" @click="banConfirmOpen = true">{{ banButtonLabel }}</button>
        </div>
      </div>
    </div>
    <div v-else-if="loading" class="h-32 skeleton" />

    <div class="flex gap-2 text-sm">
      <button class="px-3 py-1.5 rounded" :class="activeTab === 'stats' ? 'bg-primary-600 text-white' : 'bg-slate-200 dark:bg-slate-800'" @click="activeTab = 'stats'">الإحصائيات</button>
      <button class="px-3 py-1.5 rounded" :class="activeTab === 'products' ? 'bg-primary-600 text-white' : 'bg-slate-200 dark:bg-slate-800'" @click="activeTab = 'products'">المنتجات</button>
      <button class="px-3 py-1.5 rounded" :class="activeTab === 'activity' ? 'bg-primary-600 text-white' : 'bg-slate-200 dark:bg-slate-800'" @click="activeTab = 'activity'">سجل الأنشطة</button>
      <button class="px-3 py-1.5 rounded" :class="activeTab === 'subscription' ? 'bg-primary-600 text-white' : 'bg-slate-200 dark:bg-slate-800'" @click="activeTab = 'subscription'">الاشتراكات</button>
    </div>

    <div class="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-4" v-if="profile">
      <template v-if="activeTab === 'stats'">
        <div class="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
          <div class="rounded-lg border border-slate-200 dark:border-slate-800 p-3">منتجات: {{ profile.stats.products_added }}</div>
          <div class="rounded-lg border border-slate-200 dark:border-slate-800 p-3">تنبيهات: {{ profile.stats.alerts_received }}</div>
          <div class="rounded-lg border border-slate-200 dark:border-slate-800 p-3">عروض مشاهدة: {{ profile.stats.deals_viewed }}</div>
          <div class="rounded-lg border border-slate-200 dark:border-slate-800 p-3">أفعال: {{ profile.stats.total_actions }}</div>
          <div class="rounded-lg border border-slate-200 dark:border-slate-800 p-3">تتابع: {{ profile.stats.streak_days }}</div>
          <div class="rounded-lg border border-slate-200 dark:border-slate-800 p-3">طلبات متاجر: {{ profile.stats.store_requests_sent }}</div>
        </div>
      </template>

      <template v-else-if="activeTab === 'products'">
        <div class="space-y-2 text-sm">
          <div v-for="(p, i) in profile.products" :key="i" class="rounded-lg border border-slate-200 dark:border-slate-800 p-3">
            <div class="font-semibold">{{ p.name || 'منتج' }}</div>
            <div class="text-slate-500">{{ p.url }}</div>
            <div class="text-xs text-slate-500">{{ p.status }} | {{ p.alert_types?.join(', ') || '—' }}</div>
          </div>
        </div>
      </template>

      <template v-else-if="activeTab === 'activity'">
        <div class="space-y-2 text-sm">
          <div v-for="item in activityLog" :key="item.id" class="rounded-lg border border-slate-200 dark:border-slate-800 p-3">
            <div class="font-semibold">{{ item.action }}</div>
            <div class="text-slate-500">{{ JSON.stringify(item.details || {}) }}</div>
            <div class="text-xs text-slate-400">{{ formatDateTimeAr(item.created_at) }}</div>
          </div>
        </div>
      </template>

      <template v-else>
        <div class="space-y-2 text-sm">
          <div v-for="(s, i) in profile.subscription_history" :key="i" class="rounded-lg border border-slate-200 dark:border-slate-800 p-3">
            <div class="font-semibold">{{ s.details?.plan || 'unknown' }}</div>
            <div class="text-xs text-slate-400">{{ formatDateTimeAr(s.created_at) }}</div>
          </div>
        </div>
      </template>
    </div>

    <UpgradeModal
      v-model="upgradeOpen"
      :user="profile?.user"
      :loading="upgrading"
      @confirm="onUpgrade"
    />

    <BaseModal v-model="banConfirmOpen" title="⚠️ تأكيد الحظر">
      <div v-if="profile?.user" class="space-y-3 text-sm">
        <p>{{ profile.user.is_banned ? `هل تريد رفع الحظر عن @${userLabel}؟` : `هل تريد حظر @${userLabel}؟` }}</p>
        <p class="text-slate-500" v-if="!profile.user.is_banned">لن يتمكن من استخدام البوت.</p>
        <p class="text-slate-500" v-else>سيتمكن من استخدام البوت مجدداً.</p>
        <div class="flex justify-end gap-2 pt-2">
          <button class="px-3 py-2 rounded border border-slate-300 dark:border-slate-700" @click="banConfirmOpen = false">إلغاء</button>
          <button
            class="px-3 py-2 rounded text-white"
            :class="profile.user.is_banned ? 'bg-emerald-600' : 'bg-rose-600'"
            :disabled="banning"
            @click="confirmBanAction"
          >
            {{ banning ? 'جارٍ التنفيذ...' : (profile.user.is_banned ? '✅ تأكيد رفع الحظر' : '🚫 تأكيد الحظر') }}
          </button>
        </div>
      </div>
    </BaseModal>

    <BaseModal v-model="messageOpen" title="📨 إرسال رسالة مباشرة">
      <div v-if="profile?.user" class="space-y-3 text-sm">
        <p>إلى: @{{ profile.user.username || profile.user.telegram_id }} ({{ profile.user.first_name || 'بدون اسم' }})</p>
        <textarea
          v-model="messageText"
          maxlength="4096"
          rows="5"
          class="w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2"
          placeholder="اكتب رسالتك هنا..."
        />
        <p class="text-xs text-slate-500">{{ messageLength }} / 4096 حرف</p>

        <div class="space-y-2">
          <p class="text-xs text-slate-500">قوالب سريعة:</p>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="tpl in quickTemplates"
              :key="tpl.label"
              class="px-2 py-1 rounded border border-slate-300 dark:border-slate-700 text-xs"
              @click="applyTemplate(tpl.text)"
            >
              {{ tpl.label }}
            </button>
          </div>
        </div>

        <div class="rounded-lg border border-slate-200 dark:border-slate-700 p-3">
          <p class="font-semibold mb-1">معاينة:</p>
          <p>📢 رسالة من الإدارة</p>
          <p class="mt-1 whitespace-pre-wrap">{{ messagePreview }}</p>
        </div>

        <div class="flex justify-end gap-2">
          <button class="px-3 py-2 rounded border border-slate-300 dark:border-slate-700" @click="messageOpen = false">إلغاء</button>
          <button class="px-3 py-2 rounded bg-primary-600 text-white" :disabled="sending" @click="sendDirectMessage">{{ sending ? 'جارٍ الإرسال...' : '📨 إرسال الرسالة' }}</button>
        </div>
      </div>
    </BaseModal>
  </div>
</template>
