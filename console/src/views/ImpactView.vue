<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import SeriesChart from '../components/SeriesChart.vue'
import { apiJson, errorText } from '../api'
import { defang } from '../defang'
import { demoRunning } from '../demo'
import { formatTime, locale, t } from '../i18n'
import { leadHours } from '../stats'
import type { CaseDetail, ImpactStats, LeadSide, Stats } from '../types'

type Range = '24h' | '7d'

interface LeadRow {
  domain: string
  seen: string | null
  hoursToConfirm: number | null
  hours: number
  gsb: LeadSide | null
  vt: LeadSide | null
}

const MAX_LEAD = 30
const CONCURRENCY = 4

const range = ref<Range>('24h')
const impact = ref<ImpactStats | null>(null)
const loading = ref(true)
const error = ref('')
const leadRows = ref<LeadRow[]>([])
const leadLooked = ref(0)
const leadLoading = ref(false)
let generation = 0

const totals = computed(() => impact.value?.totals ?? null)
const warnBlock = computed(() => (totals.value ? totals.value.warn + totals.value.block : 0))
const blockedVisits = computed(() =>
  totals.value ? Object.values(totals.value.blocked_hits).reduce((a, b) => a + b, 0) : 0,
)
const bySource = computed(() => Object.entries(totals.value?.candidates_by_source ?? {}))
const byChannel = computed(() => Object.entries(totals.value?.blocked_hits ?? {}))

const hasVolume = computed(() =>
  (impact.value?.series ?? []).some((p) => p.checks > 0 || p.candidates > 0 || p.confirmed > 0),
)

const numberLocale = computed(() => (locale.value === 'ar' ? 'ar-AE' : 'en-GB'))

function bucketLabel(bucket: string): string {
  const d = new Date(bucket)
  if (Number.isNaN(d.getTime())) return bucket
  return range.value === '24h'
    ? d.toLocaleTimeString(numberLocale.value, { hour: '2-digit', minute: '2-digit' })
    : d.toLocaleDateString(numberLocale.value, { day: 'numeric', month: 'short' })
}

const points = computed(() =>
  (impact.value?.series ?? []).map((p) => ({
    label: bucketLabel(p.bucket),
    bars: p.checks,
    outlined: p.candidates,
    line: p.confirmed,
  })),
)

const median = computed(() => {
  const sorted = leadRows.value.map((r) => r.hours).sort((a, b) => a - b)
  if (!sorted.length) return 0
  const mid = Math.floor(sorted.length / 2)
  const m = sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2
  return Math.round(m * 10) / 10
})

function sideText(side: LeadSide | null): string {
  if (!side || side.state === 'not_polled' || side.at_least_hours === null) return t('leadNotPolled')
  return side.state === 'hit'
    ? t('leadListed', { n: side.at_least_hours })
    : t('leadNotListed', { n: side.at_least_hours })
}

async function loadLead(domains: ImpactStats['lead_domains'], mine: number): Promise<void> {
  const targets = domains.slice(0, MAX_LEAD)
  const found: LeadRow[] = []
  let next = 0
  async function worker(): Promise<void> {
    while (next < targets.length) {
      const target = targets[next++]
      try {
        const detail = await apiJson<CaseDetail>(`/v1/admin/cases/${encodeURIComponent(target.domain)}`)
        const hours = leadHours(detail.lead_time)
        if (hours !== null) {
          found.push({
            domain: target.domain,
            seen: target.seen,
            hoursToConfirm: target.hours_to_confirm,
            hours,
            gsb: detail.lead_time?.gsb ?? null,
            vt: detail.lead_time?.vt ?? null,
          })
        }
        if (mine === generation) leadLooked.value++
      } catch {
        // A case that cannot be read is skipped.
      }
    }
  }
  await Promise.all(Array.from({ length: CONCURRENCY }, worker))
  if (mine !== generation) return
  const order = new Map(domains.map((d, i) => [d.domain, i]))
  leadRows.value = found.sort((a, b) => (order.get(a.domain) ?? 0) - (order.get(b.domain) ?? 0))
  leadLoading.value = false
}

async function load(): Promise<void> {
  const mine = ++generation
  loading.value = true
  error.value = ''
  leadRows.value = []
  leadLooked.value = 0
  leadLoading.value = false
  try {
    const res = await apiJson<Stats>(`/v1/admin/stats?range=${range.value}`)
    if (mine !== generation) return
    impact.value = res.impact
    loading.value = false
    leadLoading.value = res.impact.lead_domains.length > 0
    await loadLead(res.impact.lead_domains, mine)
  } catch (e) {
    if (mine !== generation) return
    error.value = t('failed', { error: errorText(e) })
    loading.value = false
  }
}

function setRange(next: Range): void {
  if (next === range.value) return
  range.value = next
  void load()
}

onMounted(load)
// Sample figures shown during the demo go away as soon as it stops.
watch(demoRunning, (running) => {
  if (!running) void load()
})
</script>

<template>
  <div class="page-head">
    <h1>{{ t('impactTitle') }}</h1>
    <div class="seg actions">
      <button type="button" :aria-pressed="range === '24h'" @click="setRange('24h')">{{ t('range24h') }}</button>
      <button type="button" :aria-pressed="range === '7d'" @click="setRange('7d')">{{ t('range7d') }}</button>
    </div>
  </div>
  <p v-if="loading" class="muted" role="status">{{ t('loading') }}</p>
  <p v-else-if="error" class="error" role="alert">{{ error }}</p>
  <template v-else-if="impact && totals">
    <div class="stat-strip">
      <div class="stat">
        <span class="num">{{ warnBlock }}</span> {{ t('impactChecks') }}
        <span class="muted">{{ t('impactOfChecks', { n: totals.checks }) }}</span>
      </div>
      <div class="stat"><span class="num">{{ totals.candidates }}</span> {{ t('impactCandidates') }}</div>
      <div class="stat"><span class="num">{{ totals.confirmed }}</span> {{ t('impactConfirmed') }}</div>
      <div class="stat"><span class="num">{{ totals.rejected }}</span> {{ t('impactRejected') }}</div>
      <div class="stat"><span class="num">{{ totals.reports }}</span> {{ t('impactReports') }}</div>
      <div class="stat"><span class="num">{{ blockedVisits }}</span> {{ t('impactBlockedVisits') }}</div>
      <div class="stat"><span class="num">{{ totals.blocklist_size }}</span> {{ t('impactBlocklistSize') }}</div>
      <div class="stat"><span class="num">{{ totals.taken_down }}</span> {{ t('impactTakenDown') }}</div>
    </div>

    <div v-if="bySource.length || byChannel.length" class="card">
      <div v-if="bySource.length" class="card-section">
        <h2 class="section-title">{{ t('impactBySource') }}</h2>
        <dl class="kv">
          <template v-for="[name, n] in bySource" :key="name">
            <dt>{{ name }}</dt>
            <dd>{{ n }}</dd>
          </template>
        </dl>
      </div>
      <div v-if="byChannel.length" class="card-section">
        <h2 class="section-title">{{ t('impactByChannel') }}</h2>
        <dl class="kv">
          <template v-for="[name, n] in byChannel" :key="name">
            <dt>{{ name }}</dt>
            <dd>{{ n }}</dd>
          </template>
        </dl>
      </div>
    </div>

    <div class="card">
      <div class="card-section">
        <h2 class="section-title">{{ t('impactOverTime') }}</h2>
        <p v-if="!hasVolume" class="empty">{{ t('impactNoVolume') }}</p>
        <SeriesChart
          v-else
          :points="points"
          :bars-label="t('impactChecks')"
          :outlined-label="t('impactCandidates')"
          :line-label="t('impactConfirmed')"
          :label="t('impactChartLabel')"
        />
      </div>
      <div v-if="hasVolume" class="card-section">
        <table class="table">
          <thead>
            <tr>
              <th>{{ t('colPeriod') }}</th>
              <th>{{ t('impactChecks') }}</th>
              <th>{{ t('impactCandidates') }}</th>
              <th>{{ t('impactConfirmed') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(p, i) in points" :key="i">
              <td :data-label="t('colPeriod')">{{ p.label }}</td>
              <td :data-label="t('impactChecks')">{{ p.bars }}</td>
              <td :data-label="t('impactCandidates')">{{ p.outlined }}</td>
              <td :data-label="t('impactConfirmed')">{{ p.line }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="card">
      <div class="card-section">
        <h2 class="section-title">{{ t('leadTitle') }}</h2>
        <p class="muted">{{ t('leadExplain') }}</p>
        <p v-if="leadLoading" class="muted" role="status">{{ t('loading') }}</p>
        <template v-else>
          <p class="muted">{{ t('leadChecked', { n: leadLooked, total: impact.lead_domains.length }) }}</p>
          <p v-if="leadRows.length === 0" class="empty">{{ t('leadEmpty') }}</p>
          <template v-else>
            <p>{{ t('leadMedian', { n: median, cases: leadRows.length }) }}</p>
            <table class="table">
              <thead>
                <tr>
                  <th>{{ t('colDomain') }}</th>
                  <th>{{ t('leadColSeen') }}</th>
                  <th>{{ t('leadColConfirm') }}</th>
                  <th>{{ t('leadColGsb') }}</th>
                  <th>{{ t('leadColVt') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="r in leadRows" :key="r.domain">
                  <td :data-label="t('colDomain')" class="mono">
                    <RouterLink :to="`/queue/${encodeURIComponent(r.domain)}`">{{ defang(r.domain) }}</RouterLink>
                  </td>
                  <td :data-label="t('leadColSeen')">{{ r.seen ? formatTime(r.seen) : '' }}</td>
                  <td :data-label="t('leadColConfirm')">{{ r.hoursToConfirm ?? '' }}</td>
                  <td :data-label="t('leadColGsb')">{{ sideText(r.gsb) }}</td>
                  <td :data-label="t('leadColVt')">{{ sideText(r.vt) }}</td>
                </tr>
              </tbody>
            </table>
          </template>
        </template>
      </div>
    </div>
  </template>
</template>
