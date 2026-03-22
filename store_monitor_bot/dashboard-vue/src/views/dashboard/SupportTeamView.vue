<script setup>
import { onMounted, ref } from 'vue'
import {
  createSupportTeamMember,
  fetchSupportTeam,
  updateSupportTeamMember,
} from '../../api/support'
import { timeAgoAr } from '../../utils/format'

const members = ref([])
const saving = ref(false)
const editingId = ref(null)
const form = ref({
  display_name: '',
  department: 'support',
  admin_id: '',
  role: '',
  avatar_color: '#2563EB',
  is_available: true,
})

const loadMembers = async () => {
  const { data } = await fetchSupportTeam()
  members.value = data.members || []
}

const resetForm = () => {
  editingId.value = null
  form.value = {
    display_name: '',
    department: 'support',
    admin_id: '',
    role: '',
    avatar_color: '#2563EB',
    is_available: true,
  }
}

const startEdit = (member) => {
  editingId.value = member.id
  form.value = {
    display_name: member.display_name,
    department: member.department,
    admin_id: member.admin_id || '',
    role: member.role || '',
    avatar_color: member.avatar_color || '#2563EB',
    is_available: member.is_available,
  }
}

const saveMember = async () => {
  saving.value = true
  try {
    const payload = {
      ...form.value,
      admin_id: form.value.admin_id ? Number(form.value.admin_id) : null,
    }
    if (editingId.value) {
      await updateSupportTeamMember(editingId.value, payload)
    } else {
      await createSupportTeamMember(payload)
    }
    await loadMembers()
    resetForm()
  } finally {
    saving.value = false
  }
}

onMounted(loadMembers)
</script>

<template>
  <div class="space-y-4">
    <section class="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 space-y-4">
      <div class="flex items-center justify-between gap-3">
        <h3 class="text-lg font-semibold">👥 إدارة الفريق</h3>
        <button class="rounded-lg border border-slate-300 dark:border-slate-700 px-3 py-2 text-sm" @click="resetForm">تهيئة</button>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        <input v-model="form.display_name" class="rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-3 py-2" placeholder="الاسم المعروض" />
        <select v-model="form.department" class="rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-3 py-2">
          <option value="support">خدمة العملاء</option>
          <option value="billing">فريق الحسابات</option>
          <option value="technical">فريق التطوير</option>
          <option value="general">عام</option>
          <option value="management">الإدارة</option>
        </select>
        <input v-model="form.admin_id" class="rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-3 py-2" placeholder="Admin ID اختياري" />
        <input v-model="form.role" class="rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-3 py-2" placeholder="الدور الوظيفي" />
        <input v-model="form.avatar_color" class="rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-3 py-2" placeholder="#2563EB" />
        <label class="flex items-center gap-2 rounded-lg border border-slate-300 dark:border-slate-700 px-3 py-2">
          <input v-model="form.is_available" type="checkbox" />
          <span>متاح حالياً</span>
        </label>
      </div>

      <button class="rounded-lg bg-blue-600 text-white px-4 py-2 text-sm" :disabled="saving || !form.display_name.trim()" @click="saveMember">
        {{ saving ? 'جارٍ الحفظ...' : (editingId ? 'تحديث العضو' : 'إضافة عضو') }}
      </button>
    </section>

    <section class="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden">
      <div v-for="member in members" :key="member.id" class="p-4 border-b border-slate-100 dark:border-slate-800 last:border-0 flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div class="flex items-center gap-3">
          <div class="w-11 h-11 rounded-full flex items-center justify-center text-white font-semibold" :style="{ backgroundColor: member.avatar_color }">
            {{ member.display_name.slice(0, 1) }}
          </div>
          <div>
            <div class="font-semibold">{{ member.display_name }}</div>
            <div class="text-sm text-slate-500">{{ member.department }} | {{ member.role || '—' }}</div>
            <div class="text-xs text-slate-400">{{ member.tickets_handled }} تذكرة | متوسط الرد {{ member.avg_response_time }} دقيقة</div>
          </div>
        </div>

        <div class="flex items-center gap-3 text-sm">
          <span class="rounded-full px-2 py-1" :class="member.is_available ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300' : 'bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300'">
            {{ member.is_available ? 'متاح' : 'غير متاح' }}
          </span>
          <span class="text-slate-400">آخر ظهور: {{ member.last_seen ? timeAgoAr(member.last_seen) : '—' }}</span>
          <button class="rounded-lg border border-slate-300 dark:border-slate-700 px-3 py-1.5" @click="startEdit(member)">تعديل</button>
        </div>
      </div>
    </section>
  </div>
</template>