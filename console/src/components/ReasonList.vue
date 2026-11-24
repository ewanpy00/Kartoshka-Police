<script setup lang="ts">
import { lang } from '../i18n'
import type { Reason } from '../types'

defineProps<{ reasons: Reason[]; active?: string | null }>()
const emit = defineEmits<{ 'update:active': [code: string | null] }>()
</script>

<template>
  <ul class="reasons" :class="{ focusing: !!active }">
    <li
      v-for="reason in reasons" :key="reason.code" :class="{ active: active === reason.code }"
      @mouseenter="emit('update:active', reason.code)" @mouseleave="emit('update:active', null)"
    >
      <span class="weight" :class="{ negative: (reason.weight ?? 0) < 0 }">{{ (reason.weight ?? 0) > 0 ? '+' : '' }}{{ reason.weight ?? 0 }}</span>
      <span>
        <span v-if="reason.code === 'AI_ASSESSMENT' || reason.source === 'ai'" class="badge ai">AI</span>
        {{ lang === 'ar' && reason.ar ? reason.ar : reason.en }}
        <code class="muted">{{ reason.code }}</code>
      </span>
    </li>
  </ul>
</template>

<style scoped>
.reasons { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.15rem; }
.reasons li { display: grid; grid-template-columns: 2.4rem 1fr; gap: 0.5rem; padding: 0.1rem 0.25rem; border-radius: 4px; transition: background-color var(--dur-fast) ease, opacity var(--dur-fast) ease; }
.reasons.focusing li { opacity: 0.55; }
.reasons li.active { opacity: 1; background: var(--surface-2); }
.weight { font-family: var(--mono); font-weight: 700; text-align: end; color: var(--muted); }
.weight.negative { color: var(--allow); }
</style>
