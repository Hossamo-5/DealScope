<script setup>
import OpportunityRow from '../opportunities/OpportunityRow.vue'

defineProps({ items: { type: Array, default: () => [] }, loading: { type: Boolean, default: false } })
defineEmits(['approve', 'reject'])
</script>

<template>
  <div class="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-4 overflow-auto">
    <h3 class="font-semibold mb-3">الفرص</h3>
    <div v-if="loading" class="h-32 skeleton" />
    <table v-else-if="items.length" class="w-full text-sm">
      <thead>
        <tr class="text-right text-slate-500 border-b border-slate-200 dark:border-slate-800">
          <th class="py-2 px-2">#</th>
          <th class="py-2 px-2">المنتج</th>
          <th class="py-2 px-2">السعر القديم</th>
          <th class="py-2 px-2">السعر الجديد</th>
          <th class="py-2 px-2">الخصم</th>
          <th class="py-2 px-2">النقاط</th>
          <th class="py-2 px-2">الحالة</th>
          <th class="py-2 px-2">إجراء</th>
        </tr>
      </thead>
      <tbody>
        <OpportunityRow v-for="item in items" :key="item.id" :item="item" @approve="$emit('approve', $event)" @reject="$emit('reject', $event)" />
      </tbody>
    </table>
    <div v-else class="text-center text-slate-500 py-10">لا توجد فرص حالياً</div>
  </div>
</template>
