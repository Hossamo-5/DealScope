<template>
  <div class="p-6 space-y-6">
    <div class="rounded-xl border border-slate-700 bg-slate-800 p-5">
      <h1 class="text-xl font-bold text-white mb-4">🔍 محلل معرفات تيليغرام</h1>

      <label class="block text-sm text-slate-300 mb-2">الصق أي رابط أو معرف تيليغرام:</label>
      <div class="flex gap-2">
        <input
          v-model="inputValue"
          class="flex-1 px-3 py-2 rounded-lg bg-slate-900 border border-slate-600 text-slate-100"
          placeholder="https://t.me/username أو @username أو -1001234567890"
          @keyup.enter="resolveNow"
        />
        <button class="px-4 py-2 rounded-lg bg-blue-600 text-white" @click="resolveNow" :disabled="loading">
          {{ loading ? '...' : '🔍 استخراج المعرف' }}
        </button>
      </div>

      <div class="mt-4 text-xs text-slate-400 space-y-1">
        <p>✅ رابط t.me/username</p>
        <p>✅ @username</p>
        <p>✅ رقم ID</p>
        <p>✅ رابط t.me/c/xxxxx/1</p>
        <p>❌ روابط الدعوة t.me/+ تحتاج /getid</p>
      </div>

      <div class="mt-4 flex flex-wrap gap-2">
        <button class="px-2 py-1 text-xs rounded bg-slate-700 text-slate-200" @click="setExample('https://t.me/UncleNull')">https://t.me/UncleNull</button>
        <button class="px-2 py-1 text-xs rounded bg-slate-700 text-slate-200" @click="setExample('@channel_name')">@channel_name</button>
        <button class="px-2 py-1 text-xs rounded bg-slate-700 text-slate-200" @click="setExample('-1001234567890')">-1001234567890</button>
      </div>
    </div>

    <div v-if="errorMessage" class="rounded-xl border border-red-700 bg-red-900/20 p-4 text-red-300">
      ❌ {{ errorMessage }}
      <p v-if="errorSuggestion" class="text-sm mt-2 text-red-200">💡 {{ errorSuggestion }}</p>
    </div>

    <div v-if="result" class="rounded-xl border border-slate-700 bg-slate-800 p-5 space-y-4">
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-semibold text-white">{{ result.type_icon }} {{ result.type_label }}</h2>
        <button class="px-2 py-1 rounded bg-slate-700 text-xs text-slate-200" @click="copyText(String(result.id))">📋 نسخ</button>
      </div>

      <p class="text-slate-200">الاسم: {{ result.name || 'غير متاح' }}</p>
      <p class="text-slate-300">المعرف: <span class="font-mono">{{ result.id }}</span></p>
      <p v-if="result.username" class="text-slate-300">@{{ result.username }}</p>
      <p v-if="result.member_count != null" class="text-slate-300">الأعضاء: {{ result.member_count }}</p>

      <div v-if="result.suggestions?.length" class="space-y-2">
        <p class="text-sm text-slate-400">الإجراءات المقترحة:</p>
        <div class="flex flex-wrap gap-2">
          <RouterLink
            v-for="(s, idx) in result.suggestions"
            :key="idx"
            :to="s.url"
            class="px-3 py-2 rounded-lg bg-blue-600 text-white text-sm"
          >
            {{ s.label }}
          </RouterLink>
        </div>
      </div>
    </div>

    <div class="rounded-xl border border-slate-700 bg-slate-800 p-5 text-slate-300 text-sm">
      <p class="font-semibold text-slate-200 mb-2">💡 للمجموعات الخاصة:</p>
      <p>1. أضف @the_c_b_i_bot للمجموعة</p>
      <p>2. أرسل في المجموعة: /getid</p>
      <p>3. سيرد البوت بالمعرف فوراً</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { resolveTelegram } from '@/api/telegram'

const inputValue = ref('')
const loading = ref(false)
const result = ref(null)
const errorMessage = ref('')
const errorSuggestion = ref('')

function setExample(v) {
  inputValue.value = v
}

async function resolveNow() {
  const value = inputValue.value.trim()
  if (!value) return

  loading.value = true
  result.value = null
  errorMessage.value = ''
  errorSuggestion.value = ''

  try {
    const { data } = await resolveTelegram(value)
    if (!data.success) {
      errorMessage.value = data.error || 'تعذر استخراج المعرف'
      errorSuggestion.value = data.suggestion || ''
      return
    }
    result.value = data
  } catch (e) {
    errorMessage.value = e?.response?.data?.detail || 'حدث خطأ أثناء استخراج المعرف'
  } finally {
    loading.value = false
  }
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text)
  } catch (_) {
    // no-op
  }
}
</script>
