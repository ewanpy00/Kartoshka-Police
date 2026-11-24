<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { apiJson, errorText } from '../api'
import { defang } from '../defang'
import { formatTime, t, type Key } from '../i18n'
import type { AuditEntry } from '../types'

const KNOWN = new Set([
  'case.confirm',
  'case.reject',
  'case.auto_confirm',
  'case.undo_auto_confirm',
  'case.recheck',
  'watchlist.add',
  'campaign.merge',
  'takedown.pack_built',
  'takedown.sent',
])

const entries = ref<AuditEntry[]>([])
const loading = ref(true)
const error = ref('')

function actionLabel(action: string): string {
  return KNOWN.has(action) ? t(`audit.${action}` as Key) : action
}

onMounted(async () => {
  try {
    const res = await apiJson<{ entries: AuditEntry[] }>('/v1/admin/audit?limit=200')
    entries.value = res.entries
  } catch (e) {
    error.value = t('failed', { error: errorText(e) })
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="page-head">
    <h1>{{ t('auditTitle') }}</h1>
  </div>
  <p v-if="loading" class="muted" role="status">{{ t('loading') }}</p>
  <p v-else-if="error" class="error" role="alert">{{ error }}</p>
  <div v-else class="card">
    <p v-if="entries.length === 0" class="empty">{{ t('auditEmpty') }}</p>
    <table v-else class="table">
      <thead>
        <tr>
          <th>{{ t('colTime') }}</th>
          <th>{{ t('colActor') }}</th>
          <th>{{ t('colAction') }}</th>
          <th>{{ t('colTarget') }}</th>
          <th>{{ t('colReason') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="e in entries" :key="e.id">
          <td :data-label="t('colTime')">{{ formatTime(e.created_at) }}</td>
          <td :data-label="t('colActor')">{{ e.actor }}</td>
          <td :data-label="t('colAction')">{{ actionLabel(e.action) }}</td>
          <td :data-label="t('colTarget')" class="mono">{{ defang(e.target) }}</td>
          <td :data-label="t('colReason')">{{ e.reason ?? '' }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
