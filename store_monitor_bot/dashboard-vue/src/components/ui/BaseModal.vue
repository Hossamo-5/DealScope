<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="modelValue" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" @click.self="close">
        <Transition name="slide-up">
          <div v-if="modelValue" class="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-[90%] max-w-lg max-h-[85vh] overflow-y-auto p-6 relative">
            <button @click="close" class="absolute top-3 left-3 text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 text-xl">&times;</button>
            <h3 v-if="title" class="text-lg font-bold mb-4">{{ title }}</h3>
            <slot />
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
defineProps({
  modelValue: Boolean,
  title: String,
})
const emit = defineEmits(['update:modelValue'])
function close() {
  emit('update:modelValue', false)
}
</script>
