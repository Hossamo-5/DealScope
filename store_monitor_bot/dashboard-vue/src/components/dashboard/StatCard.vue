<script setup>
import { computed, ref, watch } from 'vue'
import { formatNumberAr } from '../../utils/format'

const props = defineProps({
  icon: String,
  label: String,
  value: { type: Number, default: 0 },
  loading: { type: Boolean, default: false },
  numberId: { type: String, default: '' },
})

const animated = ref(0)

watch(
  () => props.value,
  (v) => {
    const start = animated.value
    const duration = 300
    const t0 = performance.now()
    const tick = (t) => {
      const p = Math.min((t - t0) / duration, 1)
      animated.value = Math.round(start + (v - start) * p)
      if (p < 1) requestAnimationFrame(tick)
    }
    requestAnimationFrame(tick)
  },
  { immediate: true }
)

const text = computed(() => formatNumberAr(animated.value))
</script>

<template>
  <div class="stat-card rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-4">
    <p class="icon text-2xl mb-2">{{ icon }}</p>
    <p class="label text-sm text-slate-500">{{ label }}</p>
    <p v-if="loading" class="h-8 mt-2 skeleton w-24"></p>
    <p v-else :id="numberId" class="number text-2xl font-bold mt-2">{{ text }}</p>
  </div>
</template>
