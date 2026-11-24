<script setup lang="ts">
// Ranked queue (D1). J/K move, C confirms, R opens the reject reasons (1-4 pick one), D re-runs deep
// analysis, W adds to the watchlist.
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { get, onEvent } from '../api'
import CaseCard from '../components/CaseCard.vue'
import DefangedDomain from '../components/DefangedDomain.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { t } from '../i18n'
import type { QueuePage, QueueRow } from '../types'

const rows = ref<QueueRow[]>([])
const total = ref(0)
const cursor = ref<string | null>(null)
const error = ref('')
const loading = ref(false)
const selected = ref(0)
const fresh = ref(0)
const filters = ref({ source: '', band: '', brand: '', has_reports: false, auto: false })
const card = ref<InstanceType<typeof CaseCard> | null>(null)
const REJECTS = ['legitimate_site', 'not_a_scam', 'insufficient_evidence', 'duplicate'] as const

async function load(more = false) {
  loading.value = true
  error.value = ''
  try {
    const f = filters.value
    const page = await get<QueuePage>('/v1/admin/queue', {
      source: f.source, band: f.band, brand: f.brand, has_reports: f.has_reports || undefined, auto: f.auto || undefined,
      cursor: more ? cursor.value : undefined,
    })
    rows.value = more ? [...rows.value, ...page.cases] : page.cases
    total.value = page.total
    cursor.value = page.next_cursor
    if (!more) {
      selected.value = Math.min(selected.value, Math.max(rows.value.length - 1, 0))
      fresh.value = 0
    }
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

const current = computed(() => rows.value[selected.value] ?? null)

function changed(domain: string) {
  const index = rows.value.findIndex((row) => row.domain === domain)
  if (index >= 0) rows.value.splice(index, 1)
  total.value = Math.max(0, total.value - 1)
  selected.value = Math.min(selected.value, Math.max(rows.value.length - 1, 0))
}

function onKey(event: KeyboardEvent) {
  const target = event.target as HTMLElement
  if (['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName) || event.metaKey || event.ctrlKey || event.altKey) return
  const key = event.key.toLowerCase()
  if (card.value?.rejecting) {
    const n = Number(key)
    if (n >= 1 && n <= 4) card.value.reject(REJECTS[n - 1])
    if (key === 'escape') card.value.rejecting = false
    return
  }
  if (key === 'j') selected.value = Math.min(selected.value + 1, rows.value.length - 1)
  else if (key === 'k') selected.value = Math.max(selected.value - 1, 0)
  else if (key === 'c') card.value?.confirm()
  else if (key === 'r') card.value?.openReject()
  else if (key === 'd') card.value?.recheck()
  else if (key === 'w') card.value?.watchSite()
  else return
  event.preventDefault()
}

let stop: (() => void) | undefined
onMounted(() => {
  load()
  window.addEventListener('keydown', onKey)
  stop = onEvent((event) => {
    if (event.type === 'check.verdict' || event.type === 'hunter.candidate') fresh.value += 1
  })
})
onUnmounted(() => {
  window.removeEventListener('keydown', onKey)
  stop?.()
})
watch(filters, () => load(), { deep: true })
watch(selected, () => document.querySelector('tr.selected')?.scrollIntoView({ block: 'nearest' }))

function ago(value: string | null): string {
  if (!value) return '—'
  const minutes = Math.round((Date.now() - Date.parse(value)) / 60_000)
  return minutes < 60 ? `${minutes}m` : minutes < 2880 ? `${Math.round(minutes / 60)}h` : `${Math.round(minutes / 1440)}d`
}
</script>

<template>
  <main class="page">
    <div class="row">
      <h1>{{ t('queue.title') }} <span class="muted small">({{ total }})</span></h1>
      <span class="spacer" />
      <button v-if="fresh" @click="load()">+{{ fresh }} new · {{ t('common.refresh') }}</button>
      <button v-else :disabled="loading" @click="load()">{{ t('common.refresh') }}</button>
    </div>
    <div class="row filters small">
      <label>{{ t('filter.source') }}
        <select v-model="filters.source"><option value="">{{ t('filter.all') }}</option>
          <option v-for="s in ['ct', 'nrd', 'feed', 'hunter', 'user_report', 'sms', 'preview', 'watchlist', 'officer', 'batch']" :key="s" :value="s">{{ s }}</option></select></label>
      <label>{{ t('filter.band') }}
        <select v-model="filters.band"><option value="">{{ t('filter.all') }}</option><option value="block">block</option><option value="warn">warn</option></select></label>
      <label>{{ t('filter.brand') }} <input v-model.lazy="filters.brand" size="10" placeholder="tamm" /></label>
      <label><input v-model="filters.has_reports" type="checkbox" /> {{ t('filter.reports') }}</label>
      <label><input v-model="filters.auto" type="checkbox" /> {{ t('queue.auto') }}</label>
      <span class="spacer" />
      <span class="muted">{{ t('queue.shortcuts') }}</span>
    </div>
    <p v-if="error" class="error">{{ error }}</p>
    <div class="layout">
      <div class="card list scroll">
        <p v-if="!rows.length && !loading" class="muted">{{ t('queue.empty') }}</p>
        <table>
          <tr v-for="(row, i) in rows" :key="row.domain" class="clickable" :class="{ selected: i === selected }" @click="selected = i">
            <td><DefangedDomain :display="row.display" />
              <div class="muted small">{{ row.brand ?? '—' }} · {{ row.sources.join(', ') }}<template v-if="row.reports"> · {{ row.reports }} reports</template><template v-if="row.hits"> · {{ row.hits }} hits</template></div>
              <div class="muted small reason">{{ row.top_reasons[0]?.en }}</div></td>
            <td><StatusBadge :value="row.band" :score="row.score" /><div class="muted small">{{ ago(row.last_seen) }}</div></td>
          </tr>
        </table>
        <button v-if="cursor" :disabled="loading" @click="load(true)">{{ t('common.more') }}</button>
      </div>
      <div class="detail">
        <CaseCard v-if="current" ref="card" :key="current.domain" :domain="current.domain" compact @changed="changed" />
      </div>
    </div>
  </main>
</template>

<style scoped>
.filters { margin-bottom: 0.75rem; gap: 0.9rem; }
.layout { display: grid; grid-template-columns: minmax(280px, 400px) minmax(0, 1fr); gap: 1rem; align-items: start; }
@media (max-width: 900px) { .layout { grid-template-columns: minmax(0, 1fr); } }
.list { padding: 0.25rem; }
.reason { max-width: 28ch; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
