<script setup>
import StatusBadge from './StatusBadge.vue'
import { formatDateTimeAr } from '../../utils/format'

defineProps({ health: { type: Object, default: null }, loading: { type: Boolean, default: false } })
</script>

<template>
  <div class="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-4">
    <div v-if="loading" class="h-36 skeleton"></div>
    <table v-else-if="health" class="w-full text-sm">
      <thead>
        <tr class="text-right text-slate-500 border-b border-slate-200 dark:border-slate-800">
          <th class="py-2 px-2">المكون</th>
          <th class="py-2 px-2">الحالة</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(status, name) in health.components" :key="name" class="border-b border-slate-200 dark:border-slate-800">
          <td class="py-2 px-2">{{ name }}</td>
          <td class="py-2 px-2"><StatusBadge :status="status" /></td>
        </tr>
        <tr>
          <td class="py-2 px-2">آخر تحديث</td>
          <td class="py-2 px-2">{{ formatDateTimeAr(health.timestamp) }}</td>
        </tr>
      </tbody>
    </table>
    <div v-else class="text-slate-500">لا توجد بيانات</div>
  </div>
</template>
