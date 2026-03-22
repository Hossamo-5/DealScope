<script setup>
import { computed, ref } from 'vue'
import { useToast } from 'vue-toastification'
import BaseModal from '../ui/BaseModal.vue'
import BaseSelect from '../ui/BaseSelect.vue'
import { publishManualOpportunity, sendBroadcast } from '../../api/quickActions'
import { createStore } from '../../api/stores'

const props = defineProps({
  subscribersCount: { type: Number, default: 0 },
})
const emit = defineEmits(['review-requests'])
const toast = useToast()

const openManual = ref(false)
const openStore = ref(false)
const openBroadcast = ref(false)
const loading = ref(false)

const manualForm = ref({
  product_name: '',
  product_url: '',
  affiliate_url: '',
  old_price: '',
  new_price: '',
  custom_message: '',
  target_plan: 'all',
})

const storeForm = ref({
  name: '',
  base_url: '',
  connector_type: 'shopify',
})

const broadcastForm = ref({
  message: '',
  target: 'all',
})

const manualTargetOptions = [
  { value: 'all', label: 'كل المشتركين' },
  { value: 'basic', label: 'المشتركين الأساسيين فقط' },
  { value: 'pro', label: 'الاحترافيين فقط' },
]

const connectorOptions = [
  { value: 'shopify', label: 'Shopify' },
  { value: 'woocommerce', label: 'WooCommerce' },
  { value: 'custom', label: 'Custom' },
]

const broadcastTargetOptions = [
  { value: 'all', label: 'كل المشتركين النشطين' },
  { value: 'paid', label: 'خطة أساسية + احترافية فقط' },
  { value: 'pro', label: 'احترافيين فقط' },
]

const messageCount = computed(() => (broadcastForm.value.message || '').length)

const submitManual = async () => {
  loading.value = true
  try {
    const payload = {
      ...manualForm.value,
      old_price: Number(manualForm.value.old_price),
      new_price: Number(manualForm.value.new_price),
      affiliate_url: manualForm.value.affiliate_url || null,
      custom_message: manualForm.value.custom_message || null,
    }
    const { data } = await publishManualOpportunity(payload)
    toast.success(`✅ تم إرسال العرض لـ ${data.sent_count || 0} مشترك`)
    openManual.value = false
  } catch (_err) {
    toast.error('تعذر نشر العرض اليدوي')
  } finally {
    loading.value = false
  }
}

const submitStore = async () => {
  loading.value = true
  try {
    const { data } = await createStore(storeForm.value)
    toast.success(`✅ تم إضافة متجر ${data.store?.name || ''}`)
    openStore.value = false
  } catch (_err) {
    toast.error('تعذر إضافة المتجر')
  } finally {
    loading.value = false
  }
}

const submitBroadcast = async () => {
  loading.value = true
  try {
    const { data } = await sendBroadcast(broadcastForm.value)
    toast.success(`✅ تم الإرسال لـ ${data.sent || 0} مشترك (فشل: ${data.failed || 0})`)
    openBroadcast.value = false
  } catch (_err) {
    toast.error('تعذر إرسال الإعلان')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-4 space-y-2">
    <h3 class="font-semibold mb-2">إجراءات سريعة</h3>
    <button v-tooltip="'إنشاء ونشر عرض يدوي للمشتركين'" class="w-full rounded-lg bg-primary-600 text-white py-2" @click="openManual = true">نشر عرض يدوي</button>
    <button v-tooltip="'إضافة متجر جديد لقائمة المتاجر المدعومة'" class="w-full rounded-lg border border-slate-300 dark:border-slate-700 py-2" @click="openStore = true">إضافة متجر مدعوم</button>
    <button v-tooltip="'إرسال رسالة إعلانية لجميع المشتركين'" class="w-full rounded-lg border border-slate-300 dark:border-slate-700 py-2" @click="openBroadcast = true">إرسال إعلان للمشتركين</button>
    <button v-tooltip="'مراجعة طلبات إضافة المتاجر من المستخدمين'" class="w-full rounded-lg border border-slate-300 dark:border-slate-700 py-2" @click="$emit('review-requests')">مراجعة الطلبات</button>
  </div>

  <BaseModal v-model="openManual" title="📢 نشر عرض يدوي">
    <div class="space-y-3">
      <input v-model="manualForm.product_name" class="w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2" placeholder="اسم المنتج" />
      <input v-model="manualForm.product_url" class="w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2" placeholder="رابط المنتج" />
      <input v-model="manualForm.affiliate_url" class="w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2" placeholder="رابط الأفلييت (اختياري)" />
      <div class="grid grid-cols-2 gap-2">
        <input v-model="manualForm.old_price" type="number" step="0.01" class="w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2" placeholder="السعر قبل" />
        <input v-model="manualForm.new_price" type="number" step="0.01" class="w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2" placeholder="السعر بعد" />
      </div>
      <textarea v-model="manualForm.custom_message" class="w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2" rows="3" placeholder="نص إضافي (اختياري)" />
      <BaseSelect v-model="manualForm.target_plan" :options="manualTargetOptions" />
      <div class="flex justify-end gap-2">
        <button class="px-3 py-2 rounded border border-slate-300 dark:border-slate-700" @click="openManual = false">إلغاء</button>
        <button class="px-3 py-2 rounded bg-primary-600 text-white" :disabled="loading" @click="submitManual">📢 إرسال للجميع</button>
      </div>
    </div>
  </BaseModal>

  <BaseModal v-model="openStore" title="🏪 إضافة متجر مدعوم">
    <div class="space-y-3">
      <input v-model="storeForm.name" class="w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2" placeholder="اسم المتجر" />
      <input v-model="storeForm.base_url" class="w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2" placeholder="الرابط الأساسي" />
      <BaseSelect v-model="storeForm.connector_type" :options="connectorOptions" />
      <div class="flex justify-end gap-2">
        <button class="px-3 py-2 rounded border border-slate-300 dark:border-slate-700" @click="openStore = false">إلغاء</button>
        <button class="px-3 py-2 rounded bg-primary-600 text-white" :disabled="loading" @click="submitStore">✅ إضافة المتجر</button>
      </div>
    </div>
  </BaseModal>

  <BaseModal v-model="openBroadcast" title="📢 إرسال إعلان">
    <div class="space-y-3">
      <textarea v-model="broadcastForm.message" maxlength="500" class="w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2" rows="5" placeholder="اكتب إعلانك هنا..." />
      <div class="text-xs text-slate-500">{{ messageCount }}/500 حرف</div>
      <BaseSelect v-model="broadcastForm.target" :options="broadcastTargetOptions" />
      <div class="rounded-lg border border-slate-200 dark:border-slate-700 p-3 text-sm">
        <p class="font-semibold mb-1">معاينة الرسالة:</p>
        <p>📢 إعلان من Store Monitor</p>
        <p class="mt-1 whitespace-pre-wrap">{{ broadcastForm.message || '[نص الإعلان هنا]' }}</p>
      </div>
      <div class="text-sm text-slate-500">سيصل لـ: {{ subscribersCount }} مشترك</div>
      <div class="flex justify-end gap-2">
        <button class="px-3 py-2 rounded border border-slate-300 dark:border-slate-700" @click="openBroadcast = false">إلغاء</button>
        <button class="px-3 py-2 rounded bg-primary-600 text-white" :disabled="loading" @click="submitBroadcast">📢 إرسال الإعلان</button>
      </div>
    </div>
  </BaseModal>
</template>
