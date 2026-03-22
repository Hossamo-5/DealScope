<script setup>
import { formatDateAr } from '../../utils/format'

defineProps({ modelValue: { type: Boolean, default: false }, detail: { type: Object, default: null }, loading: { type: Boolean, default: false } })
defineEmits(['update:modelValue'])
</script>

<template>
  <div v-if="modelValue" class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 grid place-items-center" @click.self="$emit('update:modelValue', false)">
    <div class="bg-white dark:bg-slate-900 rounded-2xl p-5 w-full max-w-2xl max-h-[85vh] overflow-auto">
      <h3 class="text-lg font-bold mb-4">ملف المستخدم</h3>
      <div v-if="loading" class="h-32 skeleton"></div>
      <div v-else-if="detail" class="space-y-4">
        <div class="grid grid-cols-2 gap-3 text-sm">
          <div>الاسم: {{ detail.first_name || '—' }}</div>
          <div>المعرف: @{{ detail.username || '—' }}</div>
          <div>Telegram ID: {{ detail.telegram_id }}</div>
          <div>الخطة: {{ detail.plan }}</div>
          <div>انتهاء الخطة: {{ formatDateAr(detail.plan_expires_at) }}</div>
          <div>التسجيل: {{ formatDateAr(detail.created_at) }}</div>
        </div>

        <div>
          <h4 class="font-semibold mb-2">المنتجات المراقبة</h4>
          <ul class="text-sm space-y-1">
            <li v-for="p in detail.products || []" :key="p.id" class="border-b border-slate-200 dark:border-slate-800 pb-1">{{ p.name || 'منتج' }} - {{ p.url }}</li>
          </ul>
        </div>

        <div>
          <h4 class="font-semibold mb-2">سجل الاشتراك</h4>
          <ul class="text-sm space-y-1">
            <li v-for="(a, i) in detail.audit_log || []" :key="i" class="border-b border-slate-200 dark:border-slate-800 pb-1">{{ a.action }} - {{ formatDateAr(a.created_at) }}</li>
          </ul>
        </div>
      </div>
    </div>
  </div>
</template>
