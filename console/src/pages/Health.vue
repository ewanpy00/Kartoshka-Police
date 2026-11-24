<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { get } from '../api'
import { t } from '../i18n'
import type { AdminHealth } from '../types'

const health = ref<AdminHealth | null>(null)
const chain = ref<{ ok: boolean; rows: number; broken_at: number | null } | null>(null)
const error = ref('')

async function load() {
  error.value = ''
  try {
    health.value = await get<AdminHealth>('/v1/admin/health')
  } catch (e) {
    error.value = (e as Error).message
  }
}

async function verify() {
  try {
    chain.value = await get('/v1/admin/evidence/verify')
  } catch (e) {
    error.value = (e as Error).message
  }
}

onMounted(load)
</script>

<template>
  <main class="page">
    <div class="row"><h1>{{ t('health.title') }}</h1><span class="spacer" /><button @click="load">{{ t('common.refresh') }}</button>
      <button @click="verify">{{ t('hunter.chain') }}</button></div>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="chain" :class="chain.ok ? 'notice' : 'error'">Evidence chain {{ chain.ok ? 'ok' : `broken at ${chain.broken_at}` }} · {{ chain.rows }} records</p>
    <div v-if="health" class="grid cols-2">
      <div class="card">
        <h2>Pipeline</h2>
        <dl class="kv">
          <dt>redis</dt><dd>{{ health.redis }}</dd>
          <dt>deep queue</dt><dd>{{ health.deep_queue ? `${health.deep_queue.waiting} waiting · ${health.deep_queue.failed} failed · ${health.deep_queue.workers} worker(s)` : '—' }}</dd>
          <dt>checks</dt><dd>{{ health.checks.last_hour }} in the last hour · last {{ health.checks.last ? new Date(health.checks.last).toLocaleString() : '—' }}</dd>
          <dt>deep running</dt><dd>{{ health.checks.deep_running }} <span v-if="health.checks.deep_stale" class="badge block">{{ health.checks.deep_stale }} stale</span></dd>
          <dt>evidence</dt><dd>{{ health.evidence.records }} records</dd>
          <dt>blocklist version</dt><dd>{{ health.blocklist_version }}</dd>
          <dt>AI</dt><dd>{{ health.ai }}</dd>
        </dl>
      </div>
      <div class="card">
        <h2>Hunter (24 h)</h2>
        <p v-if="!Object.keys(health.hunter).length" class="muted">No candidates in the last 24 hours.</p>
        <dl class="kv">
          <template v-for="(s, source) in health.hunter" :key="source"><dt>{{ source }}</dt><dd>{{ s.last_24h }} · last {{ new Date(s.last).toLocaleString() }}</dd></template>
        </dl>
        <h2>Models</h2>
        <dl class="kv">
          <template v-for="(m, key) in health.models" :key="key"><dt>{{ key }}</dt><dd>{{ m ? `${new Date(m.updated_at).toLocaleString()}${m.score !== null ? ` · ${m.score}` : ''}` : 'missing' }}</dd></template>
        </dl>
      </div>
    </div>
  </main>
</template>
