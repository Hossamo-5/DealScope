<script setup>
import { onMounted, ref } from 'vue'
import { fetchStores } from '../../api/stores'

const stores = ref([])
const loading = ref(false)

const load = async () => {
  loading.value = true
  try {
    const { data } = await fetchStores()
    stores.value = data.stores || []
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div id="section-stores" class="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-4">
    <h3 class="font-semibold mb-3">المتاجر المدعومة</h3>
    <div v-if="loading" class="h-24 skeleton" />
    <ul v-else-if="stores.length" class="space-y-2 text-sm">
      <li v-for="(s, i) in stores" :key="i" class="border-b border-slate-200 dark:border-slate-800 pb-1">{{ s.name || s }}</li>
    </ul>
    <div v-else class="text-slate-500">لا توجد متاجر حالياً</div>
  </div>
</template>
