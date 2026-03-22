<script setup>
defineProps({ title: { type: String, default: 'لا توجد بيانات' }, subtitle: { type: String, default: 'حاول تعديل الفلاتر أو أعد المحاولة لاحقاً' } })
</script>

<template>
  <div class="rounded-xl border border-dashed border-slate-300 dark:border-slate-700 p-8 text-center text-slate-500">
    <p class="text-xl mb-2">📭</p>
    <p class="font-semibold">{{ title }}</p>
    <p class="text-sm">{{ subtitle }}</p>
  </div>
</template>
