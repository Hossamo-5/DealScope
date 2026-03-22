<script setup>
import { computed, onMounted, onUnmounted } from 'vue'
import { useHealthStore } from '../../stores/health'
import HealthTable from '../../components/health/HealthTable.vue'

const store = useHealthStore()
let intervalId

const legacyHealthHtml = computed(() => {
  const components = store.health?.components || {}
  const lines = Object.entries(components).map(([name, status]) => {
    const icon = status === 'ok' ? '✅' : (status === 'error' ? '❌' : '⚠️')
    return `${name}: ${icon} ${status}`
  })
  return lines.join('<br/>')
})

onMounted(async () => {
  await store.load()
  intervalId = setInterval(() => store.load(), 30000)
})
onUnmounted(() => clearInterval(intervalId))
</script>

<template>
  <div id="section-health" class="space-y-4">
    <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
      <div class="rounded-xl p-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-center">
        <p class="text-sm text-slate-500">Database</p>
        <p class="text-2xl mt-1">
          <span v-tooltip="store.health?.components?.database === 'ok' ? 'قاعدة البيانات تعمل بشكل طبيعي' : 'يوجد خطأ في الاتصال'">{{ store.health?.components?.database === 'ok' ? '✅' : '❌' }}</span>
        </p>
      </div>
      <div class="rounded-xl p-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-center">
        <p class="text-sm text-slate-500">Redis</p>
        <p class="text-2xl mt-1">
          <span v-tooltip="store.health?.components?.redis === 'ok' ? 'قاعدة البيانات تعمل بشكل طبيعي' : 'يوجد خطأ في الاتصال'">{{ store.health?.components?.redis === 'ok' ? '✅' : '❌' }}</span>
        </p>
      </div>
      <div class="rounded-xl p-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-center">
        <p class="text-sm text-slate-500">Scraper</p>
        <p class="text-2xl mt-1">
          <span v-tooltip="store.health?.components?.scraper === 'ok' ? 'قاعدة البيانات تعمل بشكل طبيعي' : 'الأداء منخفض - يحتاج مراجعة'">{{ store.health?.components?.scraper === 'ok' ? '✅' : '⚠️' }}</span>
        </p>
      </div>
    </div>

    <div id="health-info" class="rounded-xl p-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-sm" v-html="legacyHealthHtml"></div>

    <HealthTable :health="store.health" :loading="store.loading" />
  </div>
</template>
