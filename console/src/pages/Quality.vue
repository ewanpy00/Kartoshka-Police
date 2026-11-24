<script setup lang="ts">
// Model quality (D6): what the system said before review against the officer's decision.
import { onMounted, ref } from 'vue'
import { get } from '../api'
import { t } from '../i18n'
import type { Stats } from '../types'

const quality = ref<Stats['quality'] | null>(null)
const error = ref('')

onMounted(async () => {
  try {
    quality.value = (await get<Stats>('/v1/admin/stats', { range: '7d' })).quality
  } catch (e) {
    error.value = (e as Error).message
  }
})

function pct(value: number | null): string {
  return value === null ? '—' : `${Math.round(value * 100)}%`
}
</script>

<template>
  <main class="page">
    <h1>{{ t('quality.title') }}</h1>
    <p v-if="error" class="error">{{ error }}</p>
    <template v-if="quality">
      <div class="grid cols-4">
        <div class="card"><div class="muted small">block precision ({{ quality.days }} days)</div><div class="stat">{{ pct(quality.block_precision) }}</div></div>
        <div class="card"><div class="muted small">false blocks</div><div class="stat">{{ quality.false_blocks }}</div></div>
        <div class="card"><div class="muted small">warn confirmed</div><div class="stat">{{ pct(quality.warn_confirm_rate) }}</div></div>
        <div class="card"><div class="muted small">labels for retraining</div><div class="stat">{{ quality.labels_for_retrain }}</div></div>
      </div>
      <div class="grid cols-2" style="margin-top: 1rem">
        <div class="card">
          <h2>Verdict before review vs officer decision</h2>
          <table>
            <tr><th>system said</th><th>confirmed</th><th>cleared</th><th>other reject</th></tr>
            <tr v-for="(cell, band) in quality.by_band" :key="band">
              <td><span class="badge" :class="band">{{ band }}</span></td><td>{{ cell.confirmed }}</td><td>{{ cell.cleared }}</td><td>{{ cell.other_reject }}</td>
            </tr>
          </table>
          <p class="small muted">{{ quality.reviews }} reviews. “Cleared” is a reject as legitimate site or not a scam; those and confirms become labels for <code>make retrain</code>.</p>
        </div>
        <div class="card">
          <h2>URL model (A1)</h2>
          <p v-if="!quality.url_model" class="muted">No model trained.</p>
          <dl v-else class="kv small">
            <dt>trained</dt><dd>{{ new Date(quality.url_model.updated_at).toLocaleString() }}</dd>
            <template v-for="(value, key) in quality.url_model.metrics ?? {}" :key="key">
              <dt>{{ key }}</dt><dd>{{ Array.isArray(value) ? value.join(', ') : value }}</dd>
            </template>
          </dl>
        </div>
      </div>
    </template>
  </main>
</template>
