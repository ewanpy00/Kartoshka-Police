<script setup lang="ts">
import { ref, watch } from 'vue'
import { apiJson, errorText } from '../api'
import { demoRunning } from '../demo'
import { sampleChainRecords } from '../demoData'
import { defang } from '../defang'
import { formatTime, t } from '../i18n'
import type { Verify } from '../types'

const result = ref<Verify | null>(null)
const error = ref('')
const loading = ref(false)
const samples = sampleChainRecords()

// A result shown during the demo may be a sample, so clear it when the demo stops.
watch(demoRunning, (running) => {
  if (!running) result.value = null
})

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
  <div v-if="demoRunning" class="card chain-records">
    <div class="card-section">
      <h2 class="section-title">{{ t('chainRecentTitle') }}</h2>
    </div>
    <table class="table">
      <thead>
        <tr>
          <th>{{ t('chainColSeq') }}</th>
          <th>{{ t('domain') }}</th>
          <th>{{ t('sha256') }}</th>
          <th>{{ t('colTime') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in samples" :key="r.seq">
          <td :data-label="t('chainColSeq')" class="mono">#{{ r.seq }}</td>
          <td :data-label="t('domain')" class="mono">{{ defang(r.domain) }}</td>
          <td :data-label="t('sha256')" class="mono">{{ r.hash }}</td>
          <td :data-label="t('colTime')">{{ formatTime(r.at) }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.chain-records {
  margin-block-start: 16px;
}
</style>
