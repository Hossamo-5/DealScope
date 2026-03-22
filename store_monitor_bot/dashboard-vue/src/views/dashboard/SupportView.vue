<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BaseModal from '../../components/ui/BaseModal.vue'
import { useAuthStore } from '../../stores/auth'
import {
  assignSupportTicket,
  closeSupportTicket,
  fetchSupportStats,
  fetchSupportTicket,
  fetchSupportTeam,
  fetchSupportTickets,
  replyToSupportTicket,
  resolveSupportTicket,
  transferSupportTicket,
} from '../../api/support'
import { formatDateTimeAr, timeAgoAr } from '../../utils/format'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const tickets = ref([])
const teamMembers = ref([])
const stats = ref({ open_count: 0, in_progress: 0, waiting_user: 0, resolved_today: 0 })
const selectedTicket = ref(null)
const activeStatus = ref('all')
const replyText = ref('')
const transferDepartment = ref('support')
const transferNote = ref('')
const loading = ref(false)
const replying = ref(false)
const assignmentOpen = ref(false)
const wsConnected = ref(false)
let fallbackInterval = null
let socket = null

const statusTabs = [
  { value: 'all', label: 'الكل' },
  { value: 'open', label: 'مفتوحة' },
  { value: 'in_progress', label: 'قيد المعالجة' },
  { value: 'waiting_user', label: 'تنتظر الرد' },
  { value: 'resolved', label: 'محلولة' },
]

const quickReplies = ['مرحباً 👋', 'سنتابع معك ⏳', 'تم الحل ✅', 'شكراً 🙏']

const selectedTicketId = computed(() => Number(route.params.ticketId || selectedTicket.value?.id || 0))

const activeTicketMessages = computed(() => selectedTicket.value?.messages || [])

const availableTeamMembers = computed(() => teamMembers.value.filter((member) => member.admin_id))

const loadTickets = async () => {
  loading.value = true
  try {
    const [{ data }, statsResponse, teamResponse] = await Promise.all([
      fetchSupportTickets({ status: activeStatus.value, page: 1, limit: 50 }),
      fetchSupportStats(),
      fetchSupportTeam(),
    ])
    tickets.value = data.tickets || []

    // Update stats from status_counts in tickets response
    if (data.status_counts) {
      stats.value = {
        open_count: data.status_counts.open || 0,
        in_progress: data.status_counts.in_progress || 0,
        waiting_user: data.status_counts.waiting_user || 0,
        resolved_today: data.status_counts.resolved || 0,
      }
    } else {
      stats.value = statsResponse.data || stats.value
    }

    teamMembers.value = teamResponse.data.members || []

    const fallbackId = selectedTicketId.value || tickets.value[0]?.id
    if (fallbackId) {
      await loadTicketDetail(fallbackId, false)
    } else {
      selectedTicket.value = null
    }
  } finally {
    loading.value = false
  }
}

const loadTicketDetail = async (ticketId, updateRoute = true) => {
  const { data } = await fetchSupportTicket(ticketId)
  selectedTicket.value = data
  transferDepartment.value = data.department || 'support'
  if (updateRoute && route.params.ticketId !== String(ticketId)) {
    router.replace(`/support/${ticketId}`)
  }
  connectSocket(ticketId)
}

const ensurePollingFallback = () => {
  if (fallbackInterval) return
  fallbackInterval = setInterval(async () => {
    if (selectedTicket.value?.id) {
      await Promise.all([
        loadTicketDetail(selectedTicket.value.id, false),
        loadTickets(),
      ])
    }
  }, 10000)
}

const clearPollingFallback = () => {
  if (fallbackInterval) {
    clearInterval(fallbackInterval)
    fallbackInterval = null
  }
}

const connectSocket = (ticketId) => {
  if (socket) {
    socket.close()
    socket = null
  }
  if (!ticketId || !auth.token) return

  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
  socket = new WebSocket(`${protocol}://${window.location.host}/ws/support/${ticketId}?token=${auth.token}`)
  socket.onopen = () => {
    wsConnected.value = true
    clearPollingFallback()
  }
  socket.onmessage = async (event) => {
    try {
      const payload = JSON.parse(event.data)
      if (Number(payload.ticket_id) === Number(ticketId)) {
        await loadTicketDetail(ticketId, false)
        await loadTickets()
      }
    } catch (_err) {
      // ignore malformed payloads
    }
  }
  socket.onerror = () => {
    wsConnected.value = false
    ensurePollingFallback()
  }
  socket.onclose = () => {
    wsConnected.value = false
    ensurePollingFallback()
  }
}

const selectTicket = async (ticketId) => {
  await loadTicketDetail(ticketId)
}

const sendReply = async () => {
  if (!selectedTicket.value || !replyText.value.trim()) return
  replying.value = true
  try {
    await replyToSupportTicket(selectedTicket.value.id, replyText.value.trim())
    replyText.value = ''
    await Promise.all([
      loadTicketDetail(selectedTicket.value.id, false),
      loadTickets(),
    ])
  } finally {
    replying.value = false
  }
}

const assignToMember = async (member) => {
  if (!selectedTicket.value || !member.admin_id) return
  await assignSupportTicket(selectedTicket.value.id, member.admin_id)
  assignmentOpen.value = false
  await Promise.all([
    loadTicketDetail(selectedTicket.value.id, false),
    loadTickets(),
  ])
}

const transferTicket = async () => {
  if (!selectedTicket.value) return
  await transferSupportTicket(selectedTicket.value.id, transferDepartment.value, transferNote.value)
  transferNote.value = ''
  await Promise.all([
    loadTicketDetail(selectedTicket.value.id, false),
    loadTickets(),
  ])
}

const resolveTicket = async () => {
  if (!selectedTicket.value) return
  await resolveSupportTicket(selectedTicket.value.id)
  await Promise.all([
    loadTicketDetail(selectedTicket.value.id, false),
    loadTickets(),
  ])
}

const closeTicketItem = async () => {
  if (!selectedTicket.value) return
  await closeSupportTicket(selectedTicket.value.id)
  await Promise.all([
    loadTicketDetail(selectedTicket.value.id, false),
    loadTickets(),
  ])
}

watch(activeStatus, loadTickets)
watch(() => route.params.ticketId, async (ticketId) => {
  if (ticketId) {
    await loadTicketDetail(Number(ticketId), false)
  }
})

onMounted(loadTickets)
onUnmounted(() => {
  if (socket) socket.close()
  clearPollingFallback()
})
</script>

<template>
  <div class="space-y-4">
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
      <div class="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-3">مفتوحة: {{ stats.open_count }}</div>
      <div class="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-3">قيد المعالجة: {{ stats.in_progress }}</div>
      <div class="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-3">تنتظر الرد: {{ stats.waiting_user }}</div>
      <div class="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-3">محلولة اليوم: {{ stats.resolved_today }}</div>
    </div>

    <div class="grid grid-cols-1 xl:grid-cols-[360px,1fr] gap-4 min-h-[70vh]">
      <section class="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden">
        <div class="p-4 border-b border-slate-200 dark:border-slate-800 space-y-3">
          <div class="flex flex-wrap gap-2">
            <button
              v-for="tab in statusTabs"
              :key="tab.value"
              class="rounded-full px-3 py-1 text-sm border transition-colors"
              :class="activeStatus === tab.value ? 'bg-blue-600 text-white border-blue-600' : 'border-slate-300 dark:border-slate-700'"
              @click="activeStatus = tab.value"
            >
              {{ tab.label }}
            </button>
          </div>
        </div>

        <div v-if="loading" class="p-6 text-sm text-slate-500">جاري تحميل التذاكر...</div>
        <button
          v-for="ticket in tickets"
          :key="ticket.id"
          class="w-full text-right px-4 py-4 border-b border-slate-100 dark:border-slate-800 transition-colors hover:bg-slate-50 dark:hover:bg-slate-800/60"
          :class="selectedTicket?.id === ticket.id ? 'bg-blue-50 dark:bg-blue-900/20' : ''"
          @click="selectTicket(ticket.id)"
        >
          <div class="flex items-center justify-between gap-2">
            <div class="font-semibold">{{ ticket.ticket_number }}</div>
            <div class="text-xs text-slate-400">{{ timeAgoAr(ticket.last_message_at || ticket.created_at) }}</div>
          </div>
          <div class="mt-1 text-sm text-slate-600 dark:text-slate-300">@{{ ticket.user?.username || ticket.user?.first_name || ticket.user?.telegram_id }}</div>
          <div class="mt-1 text-xs text-slate-500 dark:text-slate-400 truncate">{{ ticket.last_message_preview || ticket.subject }}</div>
          <div class="mt-2 flex items-center gap-2 text-xs">
            <span class="rounded-full bg-slate-100 dark:bg-slate-800 px-2 py-0.5">{{ ticket.department }}</span>
            <span v-if="ticket.unread_count" class="rounded-full bg-red-500 text-white px-2 py-0.5">{{ ticket.unread_count }}</span>
          </div>
        </button>
      </section>

      <section class="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 flex flex-col overflow-hidden">
        <div v-if="!selectedTicket" class="p-8 text-center text-slate-500">اختر تذكرة من القائمة لعرض المحادثة</div>

        <template v-else>
          <header class="p-4 border-b border-slate-200 dark:border-slate-800 space-y-3">
            <div class="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div class="text-lg font-semibold">{{ selectedTicket.ticket_number }}</div>
                <div class="text-sm text-slate-500">@{{ selectedTicket.user?.username || selectedTicket.user?.first_name || selectedTicket.user?.telegram_id }}</div>
              </div>
              <div class="flex flex-wrap items-center gap-2 text-xs">
                <span class="rounded-full px-2 py-1"
                  :class="wsConnected ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300' : 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300'">
                  {{ wsConnected ? 'متصل مباشرة' : 'وضع المزامنة' }}
                </span>
                <span class="rounded-full bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300 px-2 py-1">{{ selectedTicket.status }}</span>
                <span class="rounded-full bg-slate-100 dark:bg-slate-800 px-2 py-1">{{ selectedTicket.department }}</span>
                <span v-if="selectedTicket.assignee" class="rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300 px-2 py-1">{{ selectedTicket.assignee.name }}</span>
              </div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-[1fr,220px,auto,auto] gap-2 items-center">
              <select v-model="transferDepartment" class="rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-3 py-2 text-sm">
                <option value="support">خدمة العملاء</option>
                <option value="billing">الفواتير</option>
                <option value="technical">الدعم التقني</option>
                <option value="general">عام</option>
                <option value="management">الإدارة</option>
              </select>
              <input v-model="transferNote" class="rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-3 py-2 text-sm" placeholder="ملاحظة النقل (اختياري)" />
              <button class="rounded-lg bg-slate-800 text-white px-3 py-2 text-sm" @click="transferTicket">نقل القسم</button>
              <div class="flex gap-2">
                <button class="rounded-lg bg-sky-600 text-white px-3 py-2 text-sm" @click="assignmentOpen = true">تعيين</button>
                <button class="rounded-lg bg-emerald-600 text-white px-3 py-2 text-sm" @click="resolveTicket">حل</button>
                <button class="rounded-lg bg-rose-600 text-white px-3 py-2 text-sm" @click="closeTicketItem">إغلاق</button>
              </div>
            </div>
          </header>

          <div class="flex-1 overflow-y-auto p-4 space-y-3 bg-slate-50/70 dark:bg-slate-950/40">
            <div
              v-for="message in activeTicketMessages"
              :key="message.id"
              class="max-w-3xl rounded-2xl px-4 py-3 shadow-sm"
              :class="message.sender_type === 'user'
                ? 'ml-auto bg-slate-900 text-white'
                : message.sender_type === 'admin'
                  ? 'mr-auto bg-blue-600 text-white'
                  : 'mx-auto bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-200'"
            >
              <div class="flex items-center justify-between gap-4 text-xs opacity-80 mb-1">
                <span>{{ message.sender_name || message.sender_type }}</span>
                <span>{{ formatDateTimeAr(message.created_at) }}</span>
              </div>
              <div class="whitespace-pre-wrap break-words text-sm">{{ message.content }}</div>
            </div>
          </div>

          <footer class="p-4 border-t border-slate-200 dark:border-slate-800 space-y-3">
            <div class="flex flex-wrap gap-2">
              <button
                v-for="item in quickReplies"
                :key="item"
                class="rounded-full border border-slate-300 dark:border-slate-700 px-3 py-1 text-xs"
                @click="replyText = item"
              >
                {{ item }}
              </button>
            </div>
            <div class="flex gap-3">
              <textarea v-model="replyText" rows="3" class="flex-1 rounded-xl border border-slate-300 dark:border-slate-700 bg-transparent px-4 py-3" placeholder="اكتب ردك هنا..."></textarea>
              <button class="rounded-xl bg-blue-600 text-white px-5 py-3 self-end disabled:opacity-60" :disabled="replying || !replyText.trim()" @click="sendReply">
                {{ replying ? 'جارٍ الإرسال...' : 'إرسال' }}
              </button>
            </div>
          </footer>
        </template>
      </section>
    </div>

    <BaseModal v-model="assignmentOpen" title="👥 تعيين التذكرة">
      <div class="space-y-3">
        <div
          v-for="member in availableTeamMembers"
          :key="member.id"
          class="rounded-xl border border-slate-200 dark:border-slate-700 p-4 flex items-center justify-between gap-3"
        >
          <div>
            <div class="font-semibold">{{ member.display_name }}</div>
            <div class="text-sm text-slate-500 dark:text-slate-400">{{ member.department }} | {{ member.role || 'عضو فريق' }}</div>
            <div class="text-xs mt-1" :class="member.is_available ? 'text-emerald-600 dark:text-emerald-300' : 'text-rose-600 dark:text-rose-300'">
              {{ member.is_available ? 'متاح' : 'غير متاح' }}
            </div>
          </div>
          <button
            class="rounded-lg px-3 py-2 text-sm text-white"
            :class="member.is_available ? 'bg-blue-600' : 'bg-slate-600'"
            @click="assignToMember(member)"
          >
            {{ member.is_available ? 'تعيين' : 'تعيين رغم ذلك' }}
          </button>
        </div>
      </div>
    </BaseModal>
  </div>
</template>