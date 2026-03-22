<script setup>
import { computed, onMounted, ref } from 'vue'
import { useToast } from 'vue-toastification'
import { useOpportunitiesStore } from '../../stores/opportunities'
import OpportunitiesTable from '../../components/dashboard/OpportunitiesTable.vue'
import ApproveModal from '../../components/opportunities/ApproveModal.vue'

const store = useOpportunitiesStore()
const toast = useToast()

const status = ref('new')
const query = ref('')
const minScore = ref(0)
const approving = ref(false)
const approveOpen = ref(false)
const selected = ref(null)
const filtered = computed(() => store.items.filter((item) => {
  const okName = !query.value || (item.product_name || '').toLowerCase().includes(query.value.toLowerCase())
  const okScore = Number(item.score || 0) >= Number(minScore.value)
  return okName && okScore
}))

const load = async () => {
  await store.load(status.value)
}

const openApprove = (item) => {
  selected.value = item
  approveOpen.value = true
}

const onApprove = async (payload) => {
  if (!selected.value) return
  approving.value = true
  try {
    await store.approve(selected.value.id, payload)
    toast.success('تم اعتماد وإرسال الفرصة')
    approveOpen.value = false
  } catch (_err) {
    toast.error('تعذر اعتماد الفرصة')
  } finally {
    approving.value = false
  }
}

const onReject = (item) => {
  if (!confirm('هل تريد رفض هذه الفرصة؟')) return
  store.reject(item.id)
}

onMounted(load)
</script>

<template>
  <div id="section-opportunities" class="space-y-4">
    <div class="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-4 grid grid-cols-1 md:grid-cols-4 gap-3">
      <select id="opp-filter" v-model="status" class="rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 px-3 py-2" @change="load">
        <option value="new">جديدة</option>
        <option value="approved">معتمدة</option>
        <option value="rejected">مرفوضة</option>
      </select>
      <input v-model="query" class="rounded-lg border border-slate-300 dark:border-slate-700 bg-transparent px-3 py-2" placeholder="بحث باسم المنتج" />
      <input v-model.number="minScore" type="range" min="0" max="100" class="w-full accent-blue-600 dark:accent-blue-400" />
      <div class="text-sm text-slate-500 flex items-center">الحد الأدنى للنقاط: {{ minScore }}</div>
    </div>

    <OpportunitiesTable :items="filtered" :loading="store.loading" @approve="openApprove" @reject="onReject" />
    <ApproveModal v-model="approveOpen" :opportunity="selected" :loading="approving" @confirm="onApprove" />
  </div>
</template>
