<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ChevronDownIcon, CheckIcon } from '@heroicons/vue/24/outline'

const props = defineProps({
  modelValue: { type: [String, Number], required: true },
  options: {
    type: Array,
    required: true,
  },
  placeholder: { type: String, default: 'اختر...' },
  id: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue'])
const isOpen = ref(false)
const selectRef = ref(null)

const selectedLabel = computed(() => {
  const found = props.options.find((o) => o.value === props.modelValue)
  return found ? found.label : props.placeholder
})

function select(option) {
  emit('update:modelValue', option.value)
  isOpen.value = false
}

function handleClickOutside(e) {
  if (selectRef.value && !selectRef.value.contains(e.target)) {
    isOpen.value = false
  }
}

onMounted(() => document.addEventListener('click', handleClickOutside))
onUnmounted(() => document.removeEventListener('click', handleClickOutside))
</script>

<template>
  <div class="relative" ref="selectRef">
    <button
      :id="id"
      @click="isOpen = !isOpen"
      class="flex items-center justify-between w-full px-3 py-2 text-sm rounded-lg border transition-colors bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 border-slate-300 dark:border-slate-600 hover:border-blue-500 dark:hover:border-blue-400"
      type="button"
    >
      <span>{{ selectedLabel }}</span>
      <ChevronDownIcon class="w-4 h-4 transition-transform" :class="{ 'rotate-180': isOpen }" />
    </button>

    <Transition
      enter-active-class="transition ease-out duration-100"
      enter-from-class="opacity-0 scale-95"
      enter-to-class="opacity-100 scale-100"
      leave-active-class="transition ease-in duration-75"
      leave-from-class="opacity-100 scale-100"
      leave-to-class="opacity-0 scale-95"
    >
      <div
        v-if="isOpen"
        class="dropdown-menu absolute z-50 w-full mt-1 rounded-lg border shadow-lg bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700"
      >
        <ul role="listbox" class="py-1 max-h-60 overflow-auto">
          <li
            v-for="option in options"
            :key="option.value"
            role="option"
            @click="select(option)"
            class="flex items-center px-3 py-2 text-sm cursor-pointer text-slate-700 dark:text-slate-200 hover:bg-blue-50 dark:hover:bg-blue-900/30 hover:text-blue-600 dark:hover:text-blue-400"
            :class="{
              'bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 font-medium': modelValue === option.value,
            }"
          >
            <CheckIcon v-if="modelValue === option.value" class="w-4 h-4 ml-2 text-blue-500" />
            <span :class="{ 'mr-6': modelValue !== option.value }">{{ option.label }}</span>
          </li>
        </ul>
      </div>
    </Transition>
  </div>
</template>
