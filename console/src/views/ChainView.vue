<script setup lang="ts">
import { ref } from 'vue'
import { apiJson, errorText } from '../api'
import { t } from '../i18n'
import type { Verify } from '../types'

const result = ref<Verify | null>(null)
const error = ref('')
const loading = ref(false)

async function verify() {
  error.value = ''
  loading.value = true
  try {
    result.value = await apiJson<Verify>('/v1/admin/evidence/verify')
  } catch (e) {
    result.value = null
    error.value = t('failed', { error: errorText(e) })
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="page-head">
    <h1>{{ t('navChain') }}</h1>
    <div class="actions">
      <button class="btn primary" :disabled="loading" @click="verify">{{ t('runCheck') }}</button>
    </div>
  </div>
  <p v-if="loading" class="muted" role="status">{{ t('loading') }}</p>
  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <div v-if="result" class="card card-section" role="status">
    <span v-if="result.intact" class="status-chip confirmed">{{ t('intact') }}</span>
    <span v-else class="status-chip suspected">
      {{ result.first_broken
        ? t('broken', { id: result.first_broken.id, seq: result.first_broken.seq, reason: result.first_broken.reason })
        : t('chainBrokenShort') }}
    </span>
    <p>{{ t('records', { count: result.count }) }}</p>
    <dl v-if="!result.intact && result.first_broken" class="kv">
      <dt>{{ t('evidenceTitle') }}</dt>
      <dd class="mono">{{ t('chainRecord', { n: result.first_broken.seq }) }}</dd>
      <dt>{{ t('colReason') }}</dt>
      <dd>{{ result.first_broken.reason }}</dd>
    </dl>
  </div>
</template>
