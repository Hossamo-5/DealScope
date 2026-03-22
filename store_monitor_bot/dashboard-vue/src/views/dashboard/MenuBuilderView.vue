<template>
  <div class="h-full flex flex-col">
    <PageHeader title="🎛 منشئ قائمة البوت">
      <template #actions>
        <button @click="saveMenu" :disabled="!hasChanges" class="btn-secondary">💾 حفظ التغييرات</button>
        <button @click="publishMenu" class="btn-primary">📤 نشر للبوت الآن</button>
      </template>
    </PageHeader>

    <div class="p-4 space-y-4 overflow-auto">
      <section class="rounded-xl border border-slate-700 bg-slate-800 p-4 space-y-3">
        <h3 class="text-sm font-semibold text-slate-100">🤖 إعداد البوت</h3>
        <div class="text-xs text-slate-400">التوكن الحالي:</div>
        <div class="flex items-center gap-2 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2">
          <span class="flex-1 text-slate-200 font-mono text-sm">{{ maskedToken }}</span>
          <button class="px-2 py-1 rounded bg-slate-700 text-slate-200 text-xs" @click="showToken = !showToken">👁</button>
          <button class="px-2 py-1 rounded bg-slate-700 text-slate-200 text-xs" @click="showTokenEditor = !showTokenEditor">✏️</button>
        </div>
        <div class="text-sm" :class="botConnected ? 'text-green-400' : 'text-red-400'">
          {{ botConnectionText }}
        </div>
        <div class="flex gap-2">
          <button class="btn-secondary" @click="showTokenEditor = !showTokenEditor">🔄 تغيير التوكن</button>
          <button class="btn-secondary" @click="runBotConnectionTest">📡 اختبار الاتصال</button>
        </div>

        <div v-if="showTokenEditor" class="rounded-lg border border-slate-700 bg-slate-900 p-3 space-y-2">
          <label class="text-sm text-slate-300">التوكن الجديد:</label>
          <input v-model="newToken" class="w-full px-3 py-2 rounded bg-slate-800 border border-slate-600 text-slate-100" />
          <div class="flex justify-end gap-2">
            <button class="btn-secondary" @click="cancelTokenEdit">إلغاء</button>
            <button class="btn-primary" @click="saveAndVerifyToken">✅ حفظ وتحقق</button>
          </div>
        </div>
      </section>

      <div class="flex gap-2">
        <button class="px-3 py-2 rounded-lg text-sm" :class="activeTab === 'builder' ? 'bg-blue-600 text-white' : 'bg-slate-700 text-slate-300'" @click="activeTab = 'builder'">🎛 منشئ القائمة</button>
        <button class="px-3 py-2 rounded-lg text-sm" :class="activeTab === 'resolver' ? 'bg-blue-600 text-white' : 'bg-slate-700 text-slate-300'" @click="activeTab = 'resolver'">🔍 محلل المعرفات</button>
      </div>

      <section v-if="activeTab === 'resolver'" class="rounded-xl border border-slate-700 bg-slate-800 p-4 space-y-3">
        <h3 class="text-sm font-semibold text-slate-100">🔍 محلل المعرفات</h3>
        <div class="flex gap-2">
          <input v-model="resolverInput" class="flex-1 px-3 py-2 rounded bg-slate-900 border border-slate-600 text-slate-100" placeholder="https://t.me/username أو @username أو -1001234567890" />
          <button class="btn-primary" @click="resolveInBuilder">استخراج</button>
        </div>
        <div v-if="resolverError" class="text-red-300 text-sm">❌ {{ resolverError }}</div>
        <div v-if="resolverResult" class="rounded-lg border border-slate-700 p-3">
          <div class="text-slate-100">{{ resolverResult.type_icon }} {{ resolverResult.type_label }}</div>
          <div class="text-slate-300">{{ resolverResult.name }}</div>
          <div class="text-slate-300 font-mono">{{ resolverResult.id }}</div>
          <button class="mt-2 px-2 py-1 rounded bg-slate-700 text-xs text-slate-200" @click="copyText(String(resolverResult.id))">📋 نسخ</button>
        </div>
      </section>

      <div v-if="activeTab === 'builder'" class="flex gap-4 overflow-hidden">
        <div class="w-72 flex-shrink-0">
          <div class="rounded-2xl border-4 border-slate-600 bg-slate-900 overflow-hidden shadow-2xl">
            <div class="bg-slate-800 p-3">
              <div class="bg-blue-600 rounded-2xl rounded-br-sm p-3 mb-3 text-sm text-white mr-8">القائمة الرئيسية</div>
              <div class="space-y-1.5">
                <div v-for="row in previewRows" :key="row.rowIndex" class="flex gap-1.5">
                  <button
                    v-for="btn in row.buttons"
                    :key="btn.id"
                    @click="selectButton(btn)"
                    :class="['flex-1 py-2 px-1 text-xs rounded-lg transition-all duration-150', selectedButton?.id === btn.id ? 'bg-blue-600 text-white ring-2 ring-blue-400' : 'bg-slate-700 text-slate-200 hover:bg-slate-600']"
                  >
                    {{ btn.label }}
                  </button>
                </div>
              </div>
              <button @click="addButton" class="w-full mt-2 py-2 text-xs border-2 border-dashed border-slate-600 rounded-lg text-slate-500 hover:text-slate-400 hover:border-slate-500 transition-colors">+ إضافة زرار جديد</button>
            </div>
          </div>
        </div>

        <div class="flex-1 overflow-auto">
          <div class="bg-slate-800 rounded-xl p-4 mb-4">
            <div class="flex items-center justify-between mb-3">
              <h3 class="text-sm font-semibold text-slate-200">🗂 ترتيب الأزرار</h3>
              <span class="text-xs text-slate-400">اسحب لإعادة الترتيب</span>
            </div>
            <draggable v-model="menuButtons" group="buttons" @change="onReorder" item-key="id" class="space-y-2">
              <template #item="{ element: btn }">
                <div
                  @click="selectButton(btn)"
                  :class="['flex items-center gap-3 p-3 rounded-lg cursor-grab active:cursor-grabbing border transition-all', selectedButton?.id === btn.id ? 'bg-blue-900/30 border-blue-600' : 'bg-slate-700/50 border-slate-600', !btn.is_active && 'opacity-50']"
                >
                  <span class="text-lg">{{ btn.emoji }}</span>
                  <div class="flex-1 min-w-0">
                    <p class="text-sm text-white truncate">{{ btn.label }}</p>
                    <p class="text-xs text-slate-400">{{ actionTypeLabel(btn.action_type) }}</p>
                  </div>
                  <button @click.stop="toggleActive(btn)" :class="btn.is_active ? 'text-green-400' : 'text-slate-500'">👁</button>
                  <button @click.stop="deleteButton(btn)" class="text-slate-500 hover:text-red-400">🗑</button>
                </div>
              </template>
            </draggable>
            <button @click="addButton" class="w-full mt-3 py-3 rounded-lg text-sm border-2 border-dashed border-slate-600 text-slate-400 hover:text-blue-400 hover:border-blue-500 transition-colors">➕ إضافة زرار جديد</button>
          </div>
        </div>

        <div class="w-80 flex-shrink-0">
          <div v-if="selectedButton" class="bg-slate-800 rounded-xl p-4 sticky top-0 space-y-4 max-h-full overflow-y-auto">
            <h3 class="text-sm font-semibold text-slate-200">✏️ تعديل الزرار</h3>
            <div>
              <label class="block text-xs text-slate-400 mb-1">نص الزرار:</label>
              <div class="flex gap-2">
                <button @click="showEmojiPicker = !showEmojiPicker" class="w-12 h-10 rounded-lg bg-slate-700 border border-slate-600 text-xl hover:bg-slate-600 transition-colors">{{ selectedButton.emoji || '😊' }}</button>
                <input v-model="selectedButton.label_text" type="text" class="flex-1 input-dark text-sm" />
              </div>
              <div v-if="showEmojiPicker" class="mt-2 p-2 bg-slate-700 rounded-lg grid grid-cols-8 gap-1">
                <button v-for="emoji in commonEmojis" :key="emoji" @click="selectEmoji(emoji)" class="w-8 h-8 text-lg hover:bg-slate-600 rounded transition-colors">{{ emoji }}</button>
              </div>
            </div>

            <div>
              <label class="block text-xs text-slate-400 mb-2">عند الضغط على الزرار:</label>
              <select v-model="selectedButton.action_type" class="w-full p-2 rounded-lg bg-slate-700 text-slate-200 border border-slate-600 text-sm">
                <option v-for="type in actionTypes" :key="type.value" :value="type.value">{{ type.icon }} {{ type.label }}</option>
              </select>
            </div>

            <div v-if="selectedButton.action_type === 'handler'">
              <label class="block text-xs text-slate-400 mb-1">اختر الوظيفة:</label>
              <select v-model="selectedButton.action_value" class="w-full p-2 rounded-lg bg-slate-700 text-slate-200 border border-slate-600 text-sm">
                <option v-for="h in availableHandlers" :key="h.value" :value="h.value">{{ h.label }}</option>
              </select>
            </div>
            <div v-else>
              <label class="block text-xs text-slate-400 mb-1">قيمة الإجراء:</label>
              <input v-model="selectedButton.action_value" class="w-full p-2 rounded-lg bg-slate-700 text-slate-200 border border-slate-600 text-sm" />
            </div>

            <div class="grid grid-cols-2 gap-2">
              <select v-model.number="selectedButton.row" class="p-2 rounded-lg bg-slate-700 text-slate-200 border border-slate-600 text-sm">
                <option v-for="r in rowOptions" :key="r.value" :value="r.value">{{ r.label }}</option>
              </select>
              <select v-model.number="selectedButton.col" class="p-2 rounded-lg bg-slate-700 text-slate-200 border border-slate-600 text-sm">
                <option v-for="c in colOptions" :key="c.value" :value="c.value">{{ c.label }}</option>
              </select>
            </div>

            <select v-model="selectedButton.visible_for" class="w-full p-2 rounded-lg bg-slate-700 text-slate-200 border border-slate-600 text-sm">
              <option value="all">👥 الجميع</option>
              <option value="free">🆓 مجاني فقط</option>
              <option value="basic">⭐ أساسي فقط</option>
              <option value="professional">💎 احترافي فقط</option>
              <option value="admin">🔒 المديرين فقط</option>
            </select>

            <div class="flex gap-2 pt-2 border-t border-slate-700">
              <button @click="saveButton" class="flex-1 py-2 rounded-lg text-sm bg-blue-600 hover:bg-blue-500 text-white">✅ حفظ</button>
              <button @click="deleteButton(selectedButton)" class="py-2 px-3 rounded-lg text-sm bg-red-900/30 text-red-400 border border-red-700/50">🗑</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import draggable from 'vuedraggable'
import api from '@/api/axios'
import PageHeader from '@/components/layout/PageHeader.vue'
import { getBotSettings, resolveTelegram, saveBotSettings, testBotConnection } from '@/api/telegram'

const menuButtons = ref([])
const selectedButton = ref(null)
const hasChanges = ref(false)
const showEmojiPicker = ref(false)
const activeTab = ref('builder')

const botToken = ref('')
const showToken = ref(false)
const showTokenEditor = ref(false)
const newToken = ref('')
const botConnected = ref(false)
const botConnectionText = ref('❌ غير متصل')

const resolverInput = ref('')
const resolverResult = ref(null)
const resolverError = ref('')

const commonEmojis = ['➕', '📦', '📂', '🏪', '🔥', '📊', '💳', '⚙️', '❓', '🏬', '🎧', '📢', '💡', '🎯', '🛒', '💰', '📱', '🔔', '⭐', '💎', '🆓', '👤', '🔒', '🌟', '📈', '📉', '🎁', '🏆', '✅', '❌', '⚠️', '💬']

const actionTypes = [
  { value: 'handler', icon: '⚡', label: 'وظيفة موجودة' },
  { value: 'message', icon: '💬', label: 'إرسال رسالة' },
  { value: 'url', icon: '🔗', label: 'فتح رابط' },
  { value: 'menu', icon: '📋', label: 'قائمة فرعية' },
  { value: 'support', icon: '🎧', label: 'الدعم الفني' },
  { value: 'subscribe', icon: '💳', label: 'الاشتراكات' },
]

const availableHandlers = [
  { value: 'add_product', label: '➕ إضافة منتج' },
  { value: 'my_products', label: '📦 منتجاتي' },
  { value: 'monitor_category', label: '📂 مراقبة فئة' },
  { value: 'monitor_store', label: '🏪 مراقبة متجر' },
  { value: 'best_deals', label: '🔥 أفضل العروض' },
  { value: 'reports', label: '📊 التقارير' },
  { value: 'subscription', label: '💳 الاشتراك' },
  { value: 'settings', label: '⚙️ الإعدادات' },
  { value: 'help', label: '❓ المساعدة' },
  { value: 'request_store', label: '🏬 طلب إضافة متجر' },
]

const rowOptions = Array.from({ length: 8 }, (_, i) => ({ value: i, label: `صف ${i + 1}` }))
const colOptions = [{ value: 0, label: 'يمين' }, { value: 1, label: 'يسار' }]

const previewRows = computed(() => {
  const active = menuButtons.value.filter((b) => b.is_active).sort((a, b) => a.row - b.row || a.col - b.col)
  const rows = {}
  active.forEach((btn) => {
    if (!rows[btn.row]) rows[btn.row] = { rowIndex: btn.row, buttons: [] }
    rows[btn.row].buttons.push(btn)
  })
  return Object.values(rows).sort((a, b) => a.rowIndex - b.rowIndex)
})

const maskedToken = computed(() => {
  if (!botToken.value) return 'غير مضبوط'
  if (showToken.value) return botToken.value
  return `${botToken.value.slice(0, 12)}••••••••••••`
})

onMounted(async () => {
  await Promise.all([loadMenu(), loadBotConfig()])
})

async function loadBotConfig() {
  try {
    const { data } = await getBotSettings()
    const fromSettings = data?.values?.['bot.token']
    botToken.value = fromSettings || ''
    newToken.value = botToken.value
    await runBotConnectionTest()
  } catch (_) {
    botConnectionText.value = '❌ تعذر تحميل إعدادات البوت'
    botConnected.value = false
  }
}

async function runBotConnectionTest() {
  try {
    const { data } = await testBotConnection()
    botConnected.value = !!data.connected
    if (data.connected) {
      botConnectionText.value = `✅ متصل: @${data.bot_username || ''}`
    } else {
      botConnectionText.value = `❌ فشل الاتصال: ${data.error || 'Invalid token'}`
    }
  } catch (e) {
    botConnected.value = false
    botConnectionText.value = `❌ فشل الاتصال: ${e?.response?.data?.detail || 'خطأ غير متوقع'}`
  }
}

function cancelTokenEdit() {
  newToken.value = botToken.value
  showTokenEditor.value = false
}

async function saveAndVerifyToken() {
  if (!newToken.value.trim()) return
  await saveBotSettings({ 'bot.token': newToken.value.trim() })
  botToken.value = newToken.value.trim()
  showTokenEditor.value = false
  await runBotConnectionTest()
}

async function resolveInBuilder() {
  resolverError.value = ''
  resolverResult.value = null
  try {
    const { data } = await resolveTelegram(resolverInput.value)
    if (!data.success) {
      resolverError.value = data.error || 'تعذر استخراج المعرف'
      return
    }
    resolverResult.value = data
  } catch (e) {
    resolverError.value = e?.response?.data?.detail || 'حدث خطأ أثناء الاستخراج'
  }
}

async function loadMenu() {
  const { data } = await api.get('/api/bot-menu')
  menuButtons.value = data.menu
}

function selectButton(btn) {
  selectedButton.value = { ...btn, label_text: btn.label.replace(/^\p{Emoji}/u, '').trim() }
  showEmojiPicker.value = false
}

function selectEmoji(emoji) {
  if (!selectedButton.value) return
  selectedButton.value.emoji = emoji
  selectedButton.value.label = `${emoji} ${selectedButton.value.label_text}`
  showEmojiPicker.value = false
}

function addButton() {
  const newBtn = {
    id: Date.now(),
    label: '🆕 زرار جديد',
    emoji: '🆕',
    label_text: 'زرار جديد',
    action_type: 'message',
    action_value: 'مرحباً!',
    row: previewRows.value.length,
    col: 0,
    position: menuButtons.value.length,
    is_active: true,
    visible_for: 'all',
    button_type: 'reply',
    parent_id: null,
    menu_level: 0,
    isNew: true,
  }
  menuButtons.value.push(newBtn)
  selectButton(newBtn)
  hasChanges.value = true
}

async function saveButton() {
  if (!selectedButton.value) return
  const label = selectedButton.value.emoji ? `${selectedButton.value.emoji} ${selectedButton.value.label_text}` : selectedButton.value.label_text
  const payload = { ...selectedButton.value, label }
  delete payload.label_text

  if (selectedButton.value.isNew) {
    const { data } = await api.post('/api/bot-menu', payload)
    const idx = menuButtons.value.findIndex((b) => b.id === selectedButton.value.id)
    if (idx !== -1) menuButtons.value[idx] = data
    selectedButton.value = { ...data, label_text: data.label.replace(/^\p{Emoji}/u, '').trim() }
  } else {
    await api.put(`/api/bot-menu/${selectedButton.value.id}`, payload)
  }
  hasChanges.value = true
}

async function deleteButton(btn) {
  if (!confirm(`حذف "${btn.label}"؟`)) return
  await api.delete(`/api/bot-menu/${btn.id}`)
  menuButtons.value = menuButtons.value.filter((b) => b.id !== btn.id)
  if (selectedButton.value?.id === btn.id) selectedButton.value = null
  hasChanges.value = true
}

async function toggleActive(btn) {
  btn.is_active = !btn.is_active
  await api.put(`/api/bot-menu/${btn.id}`, { is_active: btn.is_active })
  hasChanges.value = true
}

async function onReorder() {
  const reordered = menuButtons.value.map((btn, index) => ({ id: btn.id, position: index, row: btn.row, col: btn.col }))
  await api.post('/api/bot-menu/reorder', { buttons: reordered })
  hasChanges.value = true
}

async function saveMenu() {
  await loadMenu()
  hasChanges.value = false
}

async function publishMenu() {
  if (!confirm('سيتم تطبيق التغييرات على البوت فوراً. هل أنت متأكد؟')) return
  await api.post('/api/bot-menu/publish')
  alert('📤 تم نشر القائمة للبوت!')
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text)
  } catch (_) {
    // no-op
  }
}

function actionTypeLabel(type) {
  return actionTypes.find((t) => t.value === type)?.label || type
}
</script>

<style scoped>
.input-dark {
  @apply px-3 py-2 rounded-lg bg-slate-700 text-white border border-slate-600 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors;
}

.btn-secondary {
  @apply px-4 py-2 rounded-lg text-sm font-medium bg-slate-700 hover:bg-slate-600 text-slate-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed;
}

.btn-primary {
  @apply px-4 py-2 rounded-lg text-sm font-medium bg-blue-600 hover:bg-blue-500 text-white transition-colors;
}
</style>
