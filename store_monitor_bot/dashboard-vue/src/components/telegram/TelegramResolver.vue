<script setup>
import { ref } from 'vue'
import { resolveTelegram } from '@/api/telegram'

const inputValue = ref('')
const loading = ref(false)
const result = ref(null)
const errorMessage = ref('')

async function resolveNow() {
  const value = inputValue.value.trim()
  if (!value) {
    return
  }

  loading.value = true
  result.value = null
  errorMessage.value = ''

  try {
    const { data } = await resolveTelegram(value)
    if (!data?.success) {
      errorMessage.value = data?.error || 'تعذر تحليل المدخل'
      return
    }
    result.value = data
  } catch (error) {
    errorMessage.value = error?.response?.data?.detail || 'حدث خطأ أثناء الاتصال بالخادم'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="rounded-xl border border-slate-700 bg-slate-800 p-5 space-y-4">
    <h3 class="text-lg font-semibold text-white">🔍 Telegram Resolver</h3>

    <div class="flex gap-2">
      <input
        v-model="inputValue"
        class="flex-1 rounded-lg border border-slate-600 bg-slate-900 px-3 py-2 text-slate-100"
        placeholder="@username أو رابط t.me أو chat_id"
        @keyup.enter="resolveNow"
      />
      <button class="rounded-lg bg-blue-600 px-4 py-2 text-white disabled:opacity-60" :disabled="loading" @click="resolveNow">
        {{ loading ? '...' : 'تحليل' }}
      </button>
    </div>

    <p v-if="errorMessage" class="text-sm text-red-300">{{ errorMessage }}</p>

    <div v-if="result" class="rounded-lg border border-slate-600 bg-slate-900 p-4 text-sm text-slate-200 space-y-1">
      <p>النوع: {{ result.type_label || 'غير معروف' }}</p>
      <p>المعرف: <span class="font-mono">{{ result.id }}</span></p>
      <p v-if="result.username">username: @{{ result.username }}</p>
      <p v-if="result.name">الاسم: {{ result.name }}</p>
    </div>
  </div>
</template>
