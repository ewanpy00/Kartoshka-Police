<script setup lang="ts">
import { lang } from '../i18n'
import type { Reason } from '../types'

defineProps<{ reasons: Reason[] }>()
</script>

<template>
  <ul class="reasons">
    <li v-for="reason in reasons" :key="reason.code">
      <span class="weight">{{ reason.weight ?? 0 }}</span>
      <span>
        <span v-if="reason.code === 'AI_ASSESSMENT' || reason.source === 'ai'" class="badge ai">AI</span>
        {{ lang === 'ar' && reason.ar ? reason.ar : reason.en }}
        <code class="muted">{{ reason.code }}</code>
      </span>
    </li>
  </ul>
</template>

<style scoped>
.reasons { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.3rem; }
.reasons li { display: grid; grid-template-columns: 2.2rem 1fr; gap: 0.5rem; }
.weight { font-family: var(--mono); font-weight: 700; text-align: end; color: var(--muted); }
</style>
