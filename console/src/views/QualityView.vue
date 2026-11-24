<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { apiJson, errorText } from '../api'
import { defang } from '../defang'
import { demoRunning } from '../demo'
import { formatTime, t, type Key } from '../i18n'
import { disagreements, type Disagreement } from '../quality'
import type { AuditEntry, Band, QualityStats, Stats } from '../types'

const quality = ref<QualityStats | null>(null)
const loading = ref(true)
const error = ref('')
const auditCount = ref(0)
const found = ref<Disagreement[]>([])
const auditError = ref('')

const BAND_LABEL: Record<Band, Key> = {
  block: 'bandNameBlock',
  warn: 'bandNameWarn',
  allow: 'bandNameAllow',
}

function percent(value: number): string {
  return `${Math.round(value * 1000) / 10}%`
}

function bandTotal(band: Band): number {
  const row = quality.value?.by_band.find((b) => b.band === band)
  return row ? row.confirmed + row.cleared + row.other_reject : 0
}

function bandConfirmed(band: Band): number {
  return quality.value?.by_band.find((b) => b.band === band)?.confirmed ?? 0
}

const rates = computed(() => {
  const q = quality.value
  if (!q) return []
  const list: { key: Key; value: number; band: Band }[] = []
  if (q.block_precision !== null) list.push({ key: 'qualityBlockPrecision', value: q.block_precision, band: 'block' })
  if (q.warn_confirm_rate !== null) list.push({ key: 'qualityWarnConfirmRate', value: q.warn_confirm_rate, band: 'warn' })
  return list
})

const model = computed(() => quality.value?.url_model ?? null)

function text(value: string | number | null): string {
  return value === null ? t('notStated') : String(value)
}

function time(iso: string | null): string {
  return iso === null ? t('notStated') : formatTime(iso)
}

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  auditError.value = ''
  const [stats, audit] = await Promise.allSettled([
    apiJson<Stats>('/v1/admin/stats?range=7d'),
    apiJson<{ entries: AuditEntry[] }>('/v1/admin/audit?limit=500'),
  ])
  if (stats.status === 'fulfilled') quality.value = stats.value.quality
  else error.value = t('failed', { error: errorText(stats.reason) })
  if (audit.status === 'fulfilled') {
    auditCount.value = audit.value.entries.length
    found.value = disagreements(audit.value.entries)
  } else {
    auditError.value = t('failed', { error: errorText(audit.reason) })
  }
  loading.value = false
}

onMounted(load)
// Sample figures shown during the demo go away as soon as it stops.
watch(demoRunning, (running) => {
  if (!running) void load()
})
</script>

<template>
  <div class="page-head">
    <h1>{{ t('qualityTitle') }}</h1>
  </div>
  <p v-if="loading" class="muted" role="status">{{ t('loading') }}</p>
  <template v-else>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <template v-if="quality">
      <p class="muted">{{ t('qualityWindow', { n: quality.days, reviews: quality.reviews }) }}</p>
      <p v-if="quality.reviews === 0" class="empty">{{ t('qualityNoReviews') }}</p>
      <template v-else>
        <div class="card">
          <div class="card-section">
            <h2 class="section-title">{{ t('qualityBandTitle') }}</h2>
            <table class="table">
              <thead>
                <tr>
                  <th>{{ t('qualitySystemSaid') }}</th>
                  <th>{{ t('qualityConfirmed') }}</th>
                  <th>{{ t('qualityCleared') }}</th>
                  <th>{{ t('qualityOtherReject') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in quality.by_band" :key="row.band">
                  <td :data-label="t('qualitySystemSaid')">
                    <span class="badge" :class="row.band">{{ t(BAND_LABEL[row.band]) }}</span>
                  </td>
                  <td :data-label="t('qualityConfirmed')">{{ row.confirmed }}</td>
                  <td :data-label="t('qualityCleared')">{{ row.cleared }}</td>
                  <td :data-label="t('qualityOtherReject')">{{ row.other_reject }}</td>
                </tr>
              </tbody>
            </table>
            <p class="muted">{{ t('qualityClearedNote') }}</p>
          </div>
          <div class="card-section">
            <dl class="kv">
              <template v-for="rate in rates" :key="rate.key">
                <dt>{{ t(rate.key) }}</dt>
                <dd>
                  {{ percent(rate.value) }}
                  <span class="muted">({{ t('qualityOf', { a: bandConfirmed(rate.band), b: bandTotal(rate.band) }) }})</span>
                </dd>
              </template>
              <dt>{{ t('qualityFalseBlocks') }}</dt>
              <dd>{{ quality.false_blocks }}</dd>
              <dt>{{ t('qualityLabels') }}</dt>
              <dd>{{ quality.labels_for_retrain }}</dd>
            </dl>
          </div>
        </div>
      </template>
    </template>

    <div class="card">
      <div class="card-section">
        <h2 class="section-title">{{ t('disagreeTitle') }}</h2>
        <p v-if="auditError" class="error" role="alert">{{ auditError }}</p>
        <template v-else>
          <p class="muted">{{ t('disagreeScope', { n: auditCount }) }}</p>
          <p v-if="found.length === 0" class="empty">{{ t('disagreeEmpty') }}</p>
          <table v-else class="table">
            <thead>
              <tr>
                <th>{{ t('colTime') }}</th>
                <th>{{ t('colDomain') }}</th>
                <th>{{ t('disagreeColSystem') }}</th>
                <th>{{ t('disagreeColDecision') }}</th>
                <th>{{ t('colReason') }}</th>
                <th>{{ t('colActor') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="d in found" :key="d.id">
                <td :data-label="t('colTime')">{{ formatTime(d.at) }}</td>
                <td :data-label="t('colDomain')" class="mono">
                  <RouterLink :to="`/queue/${encodeURIComponent(d.domain)}`">{{ defang(d.domain) }}</RouterLink>
                </td>
                <td :data-label="t('disagreeColSystem')">
                  <span class="badge" :class="d.kind === 'block_rejected' ? 'block' : 'allow'">
                    {{ t(d.kind === 'block_rejected' ? 'bandNameBlock' : 'bandNameAllow') }}
                  </span>
                  <span v-if="d.score !== null" class="muted"> {{ d.score }}</span>
                </td>
                <td :data-label="t('disagreeColDecision')">
                  {{ t(d.kind === 'block_rejected' ? 'disagreeBlockRejected' : 'disagreeAllowConfirmed') }}
                </td>
                <td :data-label="t('colReason')">{{ d.reason ?? '' }}</td>
                <td :data-label="t('colActor')">{{ d.actor }}</td>
              </tr>
            </tbody>
          </table>
        </template>
      </div>
    </div>

    <div v-if="quality" class="card">
      <div class="card-section">
        <h2 class="section-title">{{ t('modelTitle') }}</h2>
        <p v-if="!model" class="empty">{{ t('modelNone') }}</p>
        <template v-else>
          <dl class="kv">
            <dt>{{ t('modelUpdated') }}</dt>
            <dd>{{ time(model.updated_at) }}</dd>
            <dt>{{ t('modelTrainRows') }}</dt>
            <dd>{{ text(model.train_rows) }}</dd>
            <dt>{{ t('modelHoldoutRows') }}</dt>
            <dd>{{ text(model.holdout_rows) }}</dd>
            <dt>{{ t('modelDataset') }}</dt>
            <dd>{{ text(model.dataset_name) }}</dd>
            <dt>{{ t('modelDatasetDate') }}</dt>
            <dd>{{ text(model.dataset_date) }}</dd>
            <dt>{{ t('modelHeldOut') }}</dt>
            <dd>{{ model.held_out === null ? t('notStated') : t(model.held_out ? 'yes' : 'no') }}</dd>
          </dl>
          <p v-if="model.officer_phish !== null && model.officer_benign !== null" class="muted">
            {{ t('modelOfficerLabels', { phish: model.officer_phish, benign: model.officer_benign }) }}
          </p>
          <template v-if="model.metrics.length > 0">
            <p class="muted">
              {{ model.holdout_rows === null ? t('modelSampleUnknown') : t('modelSampleNote', { n: model.holdout_rows }) }}
            </p>
            <table class="table">
              <thead>
                <tr>
                  <th>{{ t('modelMetric') }}</th>
                  <th>{{ t('modelValue') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="m in model.metrics" :key="m.name">
                  <td :data-label="t('modelMetric')">{{ m.name }}</td>
                  <td :data-label="t('modelValue')">{{ m.value }}</td>
                </tr>
              </tbody>
            </table>
          </template>
          <div v-if="model.top_features.length > 0">
            <h3 class="section-title">{{ t('modelTopFeatures') }}</h3>
            <span v-for="f in model.top_features" :key="f" class="tag">{{ f }}</span>
          </div>
        </template>
      </div>
    </div>
  </template>
</template>
