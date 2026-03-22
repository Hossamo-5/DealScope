<script setup>
import StatCard from './StatCard.vue'

const props = defineProps({
  stats: { type: Object, required: true },
  loading: { type: Boolean, default: false },
})
</script>

<template>
  <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
    <StatCard v-tooltip="'إجمالي المستخدمين المسجلين'" icon="👥" label="المشتركون" number-id="stat-users" :value="props.stats.users_count" :loading="loading" />
    <StatCard v-tooltip="'المنتجات قيد المراقبة الآن'" icon="📦" label="المنتجات" number-id="stat-products" :value="props.stats.products_count" :loading="loading" />
    <StatCard v-tooltip="'فرص تجارية تنتظر مراجعتك'" icon="💡" label="فرص جديدة" number-id="stat-opportunities" :value="props.stats.new_opportunities" :loading="loading" />
    <StatCard v-tooltip="'عدد العروض التي أُرسلت اليوم'" icon="📤" label="أُرسل اليوم" number-id="stat-sent" :value="props.stats.sent_today" :loading="loading" />
  </div>
</template>
