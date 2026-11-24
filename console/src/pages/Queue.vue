<script setup lang="ts">
// Ranked queue (D1). J/K move, C confirms, R opens the reject reasons (1-4 pick one), D re-runs deep
// analysis, W adds to the watchlist.
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { get, onEvent } from '../api'
import CaseCard from '../components/CaseCard.vue'
import DefangedDomain from '../components/DefangedDomain.vue'
import Propagation from '../components/Propagation.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { t } from '../i18n'
import { defang } from '../defang'
import { useFlash } from '../motion'
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
const { keys: flashing, flash } = useFlash()
const departing = ref<Record<string, string>>({})
const lastConfirm = ref<{ domain: string; version: number | null; at: number } | null>(null)
let confirmTimer: number | undefined

async function load(more = false) {
  loading.value = true
  error.value = ''
  try {
    const f = filters.value
    const page = await get<QueuePage>('/v1/admin/queue', {
      source: f.source, band: f.band, brand: f.brand, has_reports: f.has_reports || undefined, auto: f.auto || undefined,
      cursor: more ? cursor.value : undefined,
    })
    const known = new Set(rows.value.map((row) => row.domain))
    rows.value = more ? [...rows.value, ...page.cases] : page.cases
    if (!more && known.size) page.cases.filter((row) => !known.has(row.domain)).forEach((row) => flash(row.domain))
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

async function changed(domain: string, decision: string, version?: number | null) {
  if (decision === 'confirm') {
    lastConfirm.value = { domain, version: version ?? null, at: Date.now() }
    window.clearTimeout(confirmTimer)
    confirmTimer = window.setTimeout(() => { lastConfirm.value = null }, 6000)
  }
  departing.value = { ...departing.value, [domain]: decision }
  await nextTick()
  window.setTimeout(() => {
    const { [domain]: _gone, ...rest } = departing.value
    departing.value = rest
  }, 600)
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
    if (event.type === 'check.verdict') {
      const row = rows.value.find((r) => r.domain === event.domain)
      if (row) {
        row.score = Number(event.score)
        if (event.verdict === 'warn' || event.verdict === 'block') row.band = event.verdict
        flash(row.domain)
      }
    }
  })
})
onUnmounted(() => {
  window.removeEventListener('keydown', onKey)
  window.clearTimeout(confirmTimer)
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
      <button v-if="fresh" class="fresh" @click="load()"><span class="live-dot" />+{{ fresh }} new · {{ t('common.refresh') }}</button>
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
          <TransitionGroup tag="tbody" name="row">
          <tr v-for="(row, i) in rows" :key="row.domain" class="clickable"
              :class="[{ selected: i === selected, flash: flashing.has(row.domain) }, departing[row.domain] ? `gone-${departing[row.domain]}` : '']"
              @click="selected = i">
            <td><DefangedDomain :display="row.display" />
              <div class="muted small">{{ row.brand ?? '—' }} · {{ row.sources.join(', ') }}<template v-if="row.reports"> · {{ row.reports }} reports</template><template v-if="row.hits"> · {{ row.hits }} hits</template></div>
              <div class="muted small reason">{{ row.top_reasons[0]?.en }}</div></td>
            <td><StatusBadge :value="row.band" :score="row.score" /><div class="muted small">{{ ago(row.last_seen) }}</div></td>
          </tr>
          </TransitionGroup>
        </table>
        <button v-if="cursor" :disabled="loading" @click="load(true)">{{ t('common.more') }}</button>
      </div>
      <div class="detail">
        <Transition name="page">
          <div v-if="lastConfirm" :key="lastConfirm.at" class="confirmed">
            <div class="small muted"><DefangedDomain :display="defang(lastConfirm.domain)" /></div>
            <Propagation :version="lastConfirm.version" />
          </div>
        </Transition>
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
.confirmed { margin-bottom: 0.75rem; display: grid; gap: 0.25rem; }
.fresh { border-color: var(--accent); color: var(--accent); }
.live-dot { width: 0.5rem; height: 0.5rem; border-radius: 50%; background: var(--accent); animation: kp-blink 1.2s infinite; }
tr.gone-confirm td { background: var(--block-soft); }
tr.gone-reject td { background: var(--allow-soft); }
tr.selected td:first-child { box-shadow: inset 3px 0 0 var(--accent); }
[dir='rtl'] tr.selected td:first-child { box-shadow: inset -3px 0 0 var(--accent); }
.reason { max-width: 28ch; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
