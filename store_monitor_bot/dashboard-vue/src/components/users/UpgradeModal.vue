<script setup>
import { computed, ref, watch } from 'vue'
import { formatDateAr } from '../../utils/format'

const props = defineProps({ modelValue: { type: Boolean, default: false }, user: { type: Object, default: null }, loading: { type: Boolean, default: false } })
const emit = defineEmits(['update:modelValue', 'confirm'])

const plan = ref('basic')
const days = ref(30)
const notify = ref(true)

watch(
  () => props.user,
  (u) => {
    if (u?.plan) plan.value = u.plan
  },
  { immediate: true }
)

const expiry = computed(() => {
  const d = new Date()
  d.setDate(d.getDate() + Number(days.value || 0))
  return formatDateAr(d.toISOString())
})

const close = () => emit('update:modelValue', false)
const submit = () => emit('confirm', { plan: plan.value, days: Number(days.value), notify: notify.value })
</script>

<template>
  <div v-if="modelValue" class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 grid place-items-center" @click.self="close">
    <div class="bg-white dark:bg-slate-900 rounded-2xl p-5 w-full max-w-lg">
      <h3 class="text-lg font-bold mb-2">ترقية الاشتراك</h3>
      <p class="text-sm text-slate-500 mb-4">@{{ user?.username || user?.telegram_id }} — الخطة الحالية: {{ user?.plan }}</p>
      <div class="space-y-2">
        <label class="flex gap-2"><input v-model="plan" value="free" type="radio" /> 🆓 مجاني</label>
        <label class="flex gap-2"><input v-model="plan" value="basic" type="radio" /> ⭐ أساسي — 10 ريال</label>
        <label class="flex gap-2"><input v-model="plan" value="professional" type="radio" /> 💎 احترافي — 49 ريال</label>
      </div>
      <div class="mt-3">
        <label class="text-sm">مدة الاشتراك (يوم)</label>
        <input v-model.number="days" type="number" min="1" max="365" class="mt-1 w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-3 py-2" />
      </div>
      <p class="mt-2 text-sm text-slate-500">تنتهي في: {{ expiry }}</p>
      <label class="mt-3 flex items-center gap-2 text-sm"><input v-model="notify" type="checkbox" /> إرسال إشعار للمستخدم</label>
      <div class="mt-4 flex justify-end gap-2">
        <button class="px-4 py-2 rounded border border-slate-300 dark:border-slate-700" @click="close">إلغاء</button>
        <button class="px-4 py-2 rounded bg-primary-600 text-white" :disabled="loading" @click="submit">{{ loading ? 'جارٍ الحفظ...' : 'تأكيد الترقية' }}</button>
      </div>
    </div>
  </div>
</template>
