<script setup>
const props = defineProps({ status: { type: String, default: 'new' } })

const statusMap = {
  new: 'جديدة',
  approved: 'معتمدة',
  rejected: 'مرفوضة',
  postponed: 'مؤجلة',
}

const clsMap = {
  new: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
  approved: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300',
  rejected: 'bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300',
  postponed: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
}
</script>

<template>
  <span class="text-xs rounded-full px-2 py-1 font-semibold" :class="clsMap[status] || clsMap.new">{{ statusMap[status] || status }}</span>
</template>
