<script setup>
defineProps({ title: { type: String, required: true } })
</script>

<template>
  <div class="mb-4">
    <h2 class="text-xl font-bold">{{ title }}</h2>
    <p class="text-sm text-slate-500">الرئيسية / {{ title }}</p>
  </div>
</template>
