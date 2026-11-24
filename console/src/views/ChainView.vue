<script setup lang="ts">
import { ref } from 'vue'
import { apiJson } from '../api'
import { t } from '../i18n'
import type { Verify } from '../types'

const result = ref<Verify | null>(null)
const error = ref('')

async function verify() {
  error.value = ''
  try {
    result.value = await apiJson<Verify>('/v1/admin/evidence/verify')
  } catch (e) {
    result.value = null
    error.value = t('failed', { error: String(e) })
  }
}
</script>

<template>
  <section class="panel">
    <h1>{{ t('chain') }}</h1>
    <div class="actions">
      <button @click="verify">{{ t('runCheck') }}</button>
    </div>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <div v-if="result" role="status">
      <p>{{ t('records', { count: result.count }) }}</p>
      <p v-if="result.intact" class="notice">{{ t('intact') }}</p>
      <p v-else-if="result.first_broken" class="error">
        {{ t('broken', { id: result.first_broken.id, seq: result.first_broken.seq, reason: result.first_broken.reason }) }}
      </p>
    </div>
  </section>
</template>
