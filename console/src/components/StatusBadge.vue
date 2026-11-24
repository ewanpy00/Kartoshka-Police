<script setup lang="ts">
import { computed } from 'vue'
import { t } from '../i18n'
import type { MessageKey } from '../i18n/en'

const props = defineProps<{ value: string | null | undefined; score?: number | null }>()
const text = computed(() => {
  if (!props.value) return '—'
  const key = `status.${props.value}` as MessageKey
  const translated = t(key)
  const label = translated === key ? props.value.replace(/_/g, ' ') : translated
  return props.score !== undefined && props.score !== null ? `${label} ${props.score}` : label
})
</script>

<template>
  <span class="badge" :class="value ?? ''">{{ text }}</span>
</template>
