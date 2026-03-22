<script setup>
import UserRow from './UserRow.vue'
defineProps({ users: { type: Array, default: () => [] }, loading: { type: Boolean, default: false } })
defineEmits(['upgrade', 'detail', 'ban', 'open'])
</script>

<template>
  <div class="rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-4 overflow-auto">
    <table v-if="!loading && users.length" class="w-full text-sm">
      <thead>
        <tr class="text-right text-slate-500 border-b border-slate-200 dark:border-slate-800">
          <th class="py-2 px-2">المستخدم</th>
          <th class="py-2 px-2">Telegram ID</th>
          <th class="py-2 px-2">الخطة</th>
          <th class="py-2 px-2">الانتهاء</th>
          <th class="py-2 px-2">المنتجات</th>
          <th class="py-2 px-2">التسجيل</th>
          <th class="py-2 px-2">النشاط</th>
          <th class="py-2 px-2">أوامر</th>
        </tr>
      </thead>
      <tbody>
        <UserRow
          v-for="u in users"
          :key="u.telegram_id"
          :user="u"
          @upgrade="$emit('upgrade', $event)"
          @detail="$emit('detail', $event)"
          @ban="$emit('ban', $event)"
          @open="$emit('open', $event)"
        />
      </tbody>
    </table>
    <div v-else-if="loading" class="h-40 skeleton"></div>
    <div v-else class="text-center text-slate-500 py-10">لا يوجد مستخدمون</div>
  </div>
</template>
