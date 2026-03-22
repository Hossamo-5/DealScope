<template>
  <div class="p-6 space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-xl font-bold text-slate-100">👥 إدارة المجموعات والقنوات</h1>
      <button class="px-4 py-2 rounded-lg bg-blue-600 text-white" @click="openAdd">+ إضافة</button>
    </div>

    <div v-for="g in groups" :key="g.id" class="rounded-xl border border-slate-700 bg-slate-800 p-4 space-y-2">
      <div class="flex items-center justify-between">
        <h3 class="text-slate-100 font-semibold">{{ purposeLabel(g.purpose) }} - {{ g.name }}</h3>
        <div class="flex gap-2">
          <button class="px-2 py-1 rounded bg-slate-700 text-slate-200 text-xs" @click="startEdit(g)">✏️</button>
          <button class="px-2 py-1 rounded bg-red-800 text-red-100 text-xs" @click="removeGroup(g)">🗑</button>
        </div>
      </div>
      <p class="text-slate-300 text-sm">ID: <span class="font-mono">{{ g.chat_id }}</span></p>
      <p class="text-slate-400 text-sm">الغرض: {{ purposeLabel(g.purpose) }}</p>
      <p class="text-slate-400 text-sm">الحالة: {{ g.is_active ? '✅ مفعّل' : '⏸ غير مفعّل' }}</p>
      <button class="px-3 py-2 rounded bg-indigo-600 text-white text-sm" @click="testConnection(g)">📡 اختبار الاتصال</button>
    </div>

    <div v-if="showModal" class="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50">
      <div class="w-full max-w-2xl rounded-xl border border-slate-700 bg-slate-900 p-5 space-y-4">
        <h2 class="text-lg font-semibold text-slate-100">➕ إضافة مجموعة أو قناة</h2>

        <div class="space-y-2">
          <label class="text-sm text-slate-300">الصق الرابط أو المعرف:</label>
          <div class="flex gap-2">
            <input v-model="resolveInput" class="flex-1 px-3 py-2 rounded bg-slate-800 border border-slate-600 text-slate-100" />
            <button class="px-3 py-2 rounded bg-blue-600 text-white" @click="resolveForModal">🔍 استخراج</button>
          </div>
          <p v-if="resolveError" class="text-sm text-red-300">{{ resolveError }}</p>
        </div>

        <div v-if="resolved" class="rounded border border-slate-700 p-3 space-y-2">
          <p class="text-slate-200">المعرف: <span class="font-mono">{{ resolved.id }}</span> ✅</p>
          <p class="text-slate-300">الاسم: {{ resolved.name }}</p>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label class="block text-sm text-slate-300 mb-1">الاسم المعروض:</label>
            <input v-model="form.name" class="w-full px-3 py-2 rounded bg-slate-800 border border-slate-600 text-slate-100" />
          </div>
          <div>
            <label class="block text-sm text-slate-300 mb-1">الغرض:</label>
            <select v-model="form.purpose" class="w-full px-3 py-2 rounded bg-slate-800 border border-slate-600 text-slate-100">
              <option value="admin_alerts">🔔 تنبيهات الإدارة</option>
              <option value="support_team">🎧 فريق الدعم الفني</option>
              <option value="deals">🔥 قناة العروض</option>
              <option value="announcements">📢 قناة الإعلانات</option>
              <option value="developers">👨‍💻 فريق التطوير</option>
              <option value="accounting">💰 فريق الحسابات</option>
              <option value="custom">🔧 مخصص</option>
            </select>
          </div>
        </div>

        <div>
          <label class="block text-sm text-slate-300 mb-1">الوصف:</label>
          <textarea v-model="form.description" rows="2" class="w-full px-3 py-2 rounded bg-slate-800 border border-slate-600 text-slate-100"></textarea>
        </div>

        <div class="flex justify-end gap-2">
          <button class="px-3 py-2 rounded bg-slate-700 text-slate-200" @click="closeModal">إلغاء</button>
          <button class="px-3 py-2 rounded bg-green-600 text-white" @click="saveGroup">✅ إضافة المجموعة</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { createGroup, deleteGroup, getGroups, resolveTelegram, testGroup, updateGroup } from '@/api/telegram'

const groups = ref([])
const showModal = ref(false)
const editingId = ref(null)
const resolveInput = ref('')
const resolveError = ref('')
const resolved = ref(null)
const form = ref({
  name: '',
  chat_id: null,
  purpose: 'support_team',
  description: '',
  is_active: true,
})

onMounted(loadGroups)

async function loadGroups() {
  const { data } = await getGroups()
  groups.value = data.groups || []
}

function openAdd() {
  editingId.value = null
  resolveInput.value = ''
  resolveError.value = ''
  resolved.value = null
  form.value = { name: '', chat_id: null, purpose: 'support_team', description: '', is_active: true }
  showModal.value = true
}

function startEdit(group) {
  editingId.value = group.id
  resolved.value = { id: group.chat_id, name: group.name }
  resolveInput.value = String(group.chat_id)
  form.value = {
    name: group.name,
    chat_id: group.chat_id,
    purpose: group.purpose,
    description: group.description || '',
    is_active: group.is_active,
  }
  showModal.value = true
}

function closeModal() {
  showModal.value = false
}

async function resolveForModal() {
  resolveError.value = ''
  resolved.value = null
  try {
    const { data } = await resolveTelegram(resolveInput.value)
    if (!data.success) {
      resolveError.value = data.error || 'تعذر الاستخراج'
      return
    }
    resolved.value = data
    form.value.chat_id = data.id
    if (!form.value.name) form.value.name = data.name || String(data.id)
  } catch (e) {
    resolveError.value = e?.response?.data?.detail || 'حدث خطأ'
  }
}

async function saveGroup() {
  if (!form.value.chat_id || !form.value.name) return
  if (editingId.value) {
    await updateGroup(editingId.value, form.value)
  } else {
    await createGroup(form.value)
  }
  showModal.value = false
  await loadGroups()
}

async function removeGroup(group) {
  if (!confirm(`حذف ${group.name}؟`)) return
  await deleteGroup(group.id)
  await loadGroups()
}

async function testConnection(group) {
  const { data } = await testGroup(group.id)
  if (data.success) {
    alert(`✅ تم الإرسال (message_id: ${data.message_id})`)
  } else {
    alert(`❌ فشل الاختبار: ${data.error || 'unknown'}`)
  }
}

function purposeLabel(v) {
  return {
    admin_alerts: '🔔 مجموعة الإدارة',
    support_team: '🎧 فريق الدعم',
    deals: '🔥 قناة العروض',
    announcements: '📢 قناة الإعلانات',
    developers: '👨‍💻 فريق التطوير',
    accounting: '💰 فريق الحسابات',
    custom: '🔧 مخصص',
  }[v] || v
}
</script>
