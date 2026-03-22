<script setup>
import { ref } from 'vue'
import { getBotSettings, saveBotSettings, testBotConnection } from '@/api/telegram'

const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const form = ref({
  'bot.name': '',
  'bot.username': '',
  'bot.token': '',
})
const feedback = ref('')

async function loadSettings() {
  loading.value = true
  feedback.value = ''
  try {
    const { data } = await getBotSettings()
    const values = data?.values || {}
    form.value = {
      'bot.name': values['bot.name'] || '',
      'bot.username': values['bot.username'] || '',
      'bot.token': values['bot.token'] || '',
    }
  } catch (error) {
    feedback.value = error?.response?.data?.detail || 'تعذر تحميل إعدادات البوت'
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  feedback.value = ''
  try {
    await saveBotSettings(form.value)
    feedback.value = '✅ تم حفظ إعدادات البوت بنجاح'
  } catch (error) {
    feedback.value = error?.response?.data?.detail || 'تعذر حفظ الإعدادات'
  } finally {
    saving.value = false
  }
}

async function testConnection() {
  testing.value = true
  feedback.value = ''
  try {
    const { data } = await testBotConnection()
    feedback.value = data?.message || '✅ الاتصال ناجح'
  } catch (error) {
    feedback.value = error?.response?.data?.detail || 'فشل اختبار الاتصال'
  } finally {
    testing.value = false
  }
}

loadSettings()
</script>

<template>
  <section class="space-y-6">
    <header>
      <h1 class="text-2xl font-bold text-slate-100">🤖 إدارة البوتات</h1>
      <p class="text-slate-400 mt-1">تحديث بيانات البوت الافتراضي واختبار الاتصال مباشرة.</p>
    </header>

    <div class="rounded-xl border border-slate-700 bg-slate-800 p-6 space-y-4">
      <div v-if="loading" class="text-slate-400">جاري تحميل البيانات...</div>

      <template v-else>
        <label class="block">
          <span class="text-sm text-slate-300">اسم البوت</span>
          <input v-model="form['bot.name']" class="mt-1 w-full rounded-lg border border-slate-600 bg-slate-900 px-3 py-2 text-slate-100" />
        </label>

        <label class="block">
          <span class="text-sm text-slate-300">Username</span>
          <input v-model="form['bot.username']" class="mt-1 w-full rounded-lg border border-slate-600 bg-slate-900 px-3 py-2 text-slate-100" placeholder="my_bot" />
        </label>

        <label class="block">
          <span class="text-sm text-slate-300">Bot Token</span>
          <input v-model="form['bot.token']" class="mt-1 w-full rounded-lg border border-slate-600 bg-slate-900 px-3 py-2 text-slate-100" placeholder="123456:ABC..." />
        </label>

        <div class="flex flex-wrap gap-3">
          <button class="rounded-lg bg-blue-600 px-4 py-2 text-white disabled:opacity-50" :disabled="saving" @click="save">
            {{ saving ? 'جاري الحفظ...' : '💾 حفظ' }}
          </button>
          <button class="rounded-lg bg-emerald-600 px-4 py-2 text-white disabled:opacity-50" :disabled="testing" @click="testConnection">
            {{ testing ? 'جاري الاختبار...' : '🧪 اختبار الاتصال' }}
          </button>
        </div>
      </template>
    </div>

    <p v-if="feedback" class="rounded-lg border border-slate-700 bg-slate-800 p-4 text-sm text-slate-200">
      {{ feedback }}
    </p>
  </section>
</template>
