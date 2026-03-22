<script setup>
const props = defineProps({ status: { type: String, default: 'unknown' } })
const icon = props.status === 'ok' ? '✅' : props.status === 'error' ? '❌' : '⚠️'
</script>

<template>
  <span class="text-xs rounded-full px-2 py-1 bg-slate-100 dark:bg-slate-800">{{ icon }} {{ status }}</span>
</template>
