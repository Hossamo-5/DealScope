<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useToast } from 'vue-toastification'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const toast = useToast()

const mode = ref('telegram')
const identifier = ref('')
const password = ref('')
const showPassword = ref(false)
const loading = ref(false)
const error = ref('')
const remember = ref(auth.rememberMe)

const inputClass = 'w-full rounded-lg bg-slate-700 border border-slate-600 text-white placeholder-slate-400 px-3 py-2 outline-none transition-colors focus:border-blue-500 focus:ring-1 focus:ring-blue-500'

const sanitizeTelegramId = () => {
  identifier.value = String(identifier.value || '').replace(/\D/g, '')
}

const onSubmit = async () => {
  error.value = ''
  loading.value = true
  try {
    let payload = {}

    if (mode.value === 'telegram') {
      const tid = Number(identifier.value)
      if (!Number.isInteger(tid)) {
        error.value = 'أدخل رقم Telegram ID صحيح'
        return
      }
      payload = { telegram_id: tid, password: password.value }
    } else if (mode.value === 'email') {
      payload = { email: identifier.value, password: password.value }
    } else {
      payload = { phone: identifier.value, password: password.value }
    }

    await auth.login(payload, remember.value)
    toast.success('تم تسجيل الدخول بنجاح')
    router.push('/')
  } catch (err) {
    error.value = err?.response?.data?.detail || 'فشل تسجيل الدخول. تأكد من البيانات.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div id="login-section" class="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center p-4">
    <div class="w-full max-w-md rounded-2xl bg-slate-900 border border-slate-800 p-6 shadow-2xl">
      <h1 class="text-2xl font-bold text-center mb-2">لوحة التحكم</h1>
      <p class="text-center text-slate-400 mb-6">تسجيل الدخول للإدارة</p>

      <div class="grid grid-cols-2 gap-2 mb-4">
        <div class="py-2 rounded-lg text-center cursor-pointer" :class="mode === 'telegram' ? 'bg-primary-600 text-white' : 'bg-slate-800'" @click="mode = 'telegram'">تيليغرام</div>
        <div class="py-2 rounded-lg text-center cursor-pointer" :class="mode === 'email' ? 'bg-primary-600 text-white' : 'bg-slate-800'" @click="mode = 'email'">البريد</div>
      </div>

      <form class="space-y-4" @submit.prevent="onSubmit">
        <input
          id="login-tid"
          v-model="identifier"
          :type="mode === 'telegram' ? 'text' : 'text'"
          :inputmode="mode === 'telegram' ? 'numeric' : 'text'"
          :pattern="mode === 'telegram' ? '[0-9]*' : undefined"
          :class="inputClass"
          :placeholder="mode === 'telegram' ? 'Telegram ID' : 'البريد الإلكتروني'"
          @input="mode === 'telegram' ? sanitizeTelegramId() : null"
        />
        <div class="relative">
          <input v-model="password" :type="showPassword ? 'text' : 'password'" :class="inputClass" placeholder="كلمة المرور" />
          <span class="absolute left-2 top-2 text-xs text-slate-300 cursor-pointer" @click="showPassword = !showPassword">{{ showPassword ? 'إخفاء' : 'إظهار' }}</span>
        </div>
        <label class="flex items-center gap-2 text-sm text-slate-300">
          <input v-model="remember" type="checkbox" class="accent-primary-500" />
          تذكرني
        </label>

        <p id="login-error" class="text-red-400 text-sm min-h-5">{{ error }}</p>

        <button type="submit" class="w-full rounded-lg bg-primary-600 hover:bg-primary-700 py-2 font-semibold disabled:opacity-50" :disabled="loading">
          <span v-if="loading">جارٍ الدخول...</span>
          <span v-else>دخول</span>
        </button>
      </form>
    </div>
  </div>
</template>

<style scoped>
input[type="number"]::-webkit-outer-spin-button,
input[type="number"]::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

input[type="number"] {
  -moz-appearance: textfield;
  appearance: textfield;
}
</style>
