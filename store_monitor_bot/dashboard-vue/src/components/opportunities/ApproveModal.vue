<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  opportunity: { type: Object, default: null },
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'confirm'])

const affiliateUrl = ref('')
const customMessage = ref('')

watch(
  () => props.modelValue,
  (v) => {
    if (v) {
      affiliateUrl.value = ''
      customMessage.value = ''
    }
  }
)

const close = () => emit('update:modelValue', false)
const confirm = () => emit('confirm', { affiliate_url: affiliateUrl.value, custom_message: customMessage.value })
</script>

<template>
  <div v-if="modelValue" class="fixed inset-0 bg-black/50 backdrop-blur-sm grid place-items-center z-50" @click.self="close">
    <div class="bg-white dark:bg-slate-900 rounded-2xl p-5 w-full max-w-xl">
      <h3 class="font-bold text-lg mb-3">اعتماد الفرصة</h3>
      <p class="text-sm text-slate-500 mb-3">{{ opportunity?.product_name || 'منتج' }}</p>
      <div class="space-y-3">
        <input v-model="affiliateUrl" class="w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-3 py-2" placeholder="رابط الأفلييت (اختياري)" />
        <textarea v-model="customMessage" rows="3" class="w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-3 py-2" placeholder="تخصيص الرسالة (اختياري)"></textarea>
      </div>
      <div class="mt-4 flex justify-end gap-2">
        <button class="px-4 py-2 rounded border border-slate-300 dark:border-slate-700" @click="close">إلغاء</button>
        <button class="px-4 py-2 rounded bg-emerald-600 text-white" :disabled="loading" @click="confirm">{{ loading ? 'جارٍ التنفيذ...' : 'اعتماد وإرسال' }}</button>
      </div>
    </div>
  </div>
</template>
