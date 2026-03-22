<script setup>
import { onMounted, ref } from 'vue'
import { useToast } from 'vue-toastification'
import BaseSelect from '../../components/ui/BaseSelect.vue'
import BaseModal from '../../components/ui/BaseModal.vue'
import { fetchStoreRequests, approveStoreRequest, rejectStoreRequest } from '../../api/storeRequests'

const toast = useToast()
const loading = ref(false)
const requests = ref([])
const pendingCount = ref(0)
const status = ref('pending')
const selected = ref(null)
const detailOpen = ref(false)

const statusOptions = [
  { value: 'pending', label: 'قيد الانتظار' },
  { value: 'approved', label: 'معتمد' },
  { value: 'rejected', label: 'مرفوض' },
  { value: 'all', label: 'الكل' },
]

const load = async () => {
  loading.value = true
  try {
    const { data } = await fetchStoreRequests(status.value)
    requests.value = data.requests || []
    pendingCount.value = data.pending_count || 0
  } finally {
    loading.value = false
  }
}

const openDetail = (row) => {
  selected.value = row
  detailOpen.value = true
}

const approve = async (row) => {
  try {
    await approveStoreRequest(row.id)
    toast.success('✅ تم اعتماد الطلب')
    await load()
  } catch (_err) {
    toast.error('تعذر اعتماد الطلب')
  }
}

const reject = async (row) => {
  try {
    await rejectStoreRequest(row.id)
    toast.success('❌ تم رفض الطلب')
    await load()
  } catch (_err) {
    toast.error('تعذر رفض الطلب')
  }
}

onMounted(load)
</script>

<template>
  <div class="space-y-4">
    <div class="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-4 flex items-center justify-between gap-3">
      <h3 class="font-semibold">طلبات المتاجر</h3>
      <div class="flex items-center gap-3">
        <span class="text-sm text-slate-500">المعلقة: {{ pendingCount }}</span>
        <div class="w-56">
          <BaseSelect v-model="status" :options="statusOptions" @update:model-value="load" />
        </div>
      </div>
    </div>

    <div class="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-4 overflow-auto">
      <table v-if="!loading && requests.length" class="w-full text-sm">
        <thead>
          <tr class="text-right text-slate-500 border-b border-slate-200 dark:border-slate-800">
            <th class="py-2 px-2">المستخدم</th>
            <th class="py-2 px-2">الرابط</th>
            <th class="py-2 px-2">التاريخ</th>
            <th class="py-2 px-2">الحالة</th>
            <th class="py-2 px-2">أوامر</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in requests" :key="row.id" class="border-b border-slate-200 dark:border-slate-800">
            <td class="py-2 px-2">@{{ row.user?.username || row.user?.first_name || row.user?.telegram_id }}</td>
            <td class="py-2 px-2 max-w-[360px] truncate">{{ row.store_url }}</td>
            <td class="py-2 px-2">{{ row.created_at }}</td>
            <td class="py-2 px-2">{{ row.status }}</td>
            <td class="py-2 px-2 space-x-2 space-x-reverse">
              <button v-tooltip="'اعتماد طلب المتجر'" class="rounded bg-emerald-600 text-white px-2 py-1 text-xs" @click="approve(row)">✅</button>
              <button v-tooltip="'رفض طلب المتجر'" class="rounded bg-rose-600 text-white px-2 py-1 text-xs" @click="reject(row)">❌</button>
              <button v-tooltip="'عرض تفاصيل الطلب'" class="rounded bg-slate-600 text-white px-2 py-1 text-xs" @click="openDetail(row)">👁</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else-if="loading" class="h-40 skeleton"></div>
      <div v-else class="text-center text-slate-500 py-10">لا توجد طلبات</div>
    </div>

    <BaseModal v-model="detailOpen" title="تفاصيل الطلب">
      <div v-if="selected" class="space-y-2 text-sm">
        <p><strong>المستخدم:</strong> @{{ selected.user?.username || selected.user?.first_name || selected.user?.telegram_id }}</p>
        <p><strong>الرابط:</strong> {{ selected.store_url }}</p>
        <p><strong>الحالة:</strong> {{ selected.status }}</p>
        <p><strong>ملاحظات:</strong> {{ selected.admin_notes || '—' }}</p>
      </div>
    </BaseModal>
  </div>
</template>
