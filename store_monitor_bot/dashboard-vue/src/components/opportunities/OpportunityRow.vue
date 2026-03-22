<script setup>
import { computed } from 'vue'
import OpportunityBadge from './OpportunityBadge.vue'
import { formatNumberAr } from '../../utils/format'

const props = defineProps({ item: { type: Object, required: true } })
defineEmits(['approve', 'reject'])

const scoreLabel = computed(() => {
  const s = Number(props.item.score || 0)
  if (s >= 90) return '🔥'
  if (s >= 70) return '✅'
  return 'ℹ️'
})
</script>

<template>
  <tr class="border-b border-slate-200 dark:border-slate-800">
    <td class="py-2 px-2">{{ item.id }}</td>
    <td class="py-2 px-2">{{ item.product_name || 'غير معروف' }}</td>
    <td class="py-2 px-2">{{ formatNumberAr(item.old_price) }}</td>
    <td class="py-2 px-2 font-semibold">{{ formatNumberAr(item.new_price) }}</td>
    <td class="py-2 px-2"><span class="rounded-full px-2 py-1 text-xs bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300">{{ formatNumberAr(item.discount_percent) }}%</span></td>
    <td class="py-2 px-2">{{ scoreLabel }} {{ formatNumberAr(item.score) }}</td>
    <td class="py-2 px-2"><OpportunityBadge :status="item.status" /></td>
    <td class="py-2 px-2 space-x-2 space-x-reverse">
      <button v-tooltip="'اعتماد الفرصة وإرسالها للمشتركين'" class="rounded bg-emerald-600 text-white px-2 py-1 text-xs" @click="$emit('approve', item)">✅</button>
      <button v-tooltip="'رفض هذه الفرصة'" class="rounded bg-rose-600 text-white px-2 py-1 text-xs" @click="$emit('reject', item)">❌</button>
    </td>
  </tr>
</template>
