<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { apiJson, errorText, postJson } from '../api'
import CaseCard from '../components/CaseCard.vue'
import StatStrip from '../components/StatStrip.vue'
import { band, isHigh } from '../bands'
import { defang } from '../defang'
import { demoRunning } from '../demo'
import { isDemoOnly } from '../demoData'
import { formatAge, t } from '../i18n'
import { rowTagText } from '../rowTag'
import { officerName } from '../session'
import { refreshStats, startMedianLead } from '../stats'
import type { CaseSummary } from '../types'

interface CardApi {
  armConfirm(): void
  commitConfirm(): boolean
  cancelConfirm(): void
  isArmed(): boolean
  focusReject(): void
}

const PAGE = 50
const route = useRoute()
const router = useRouter()
const card = ref<CardApi | null>(null)
const open = ref<CaseSummary[]>([])
const auto = ref<CaseSummary[]>([])
const error = ref('')
const loaded = ref(false)
const search = ref('')
const chip = ref<string>('all')
const limit = ref(PAGE)
let startedMedian = false

const selected = computed(() => (route.params.domain as string | undefined) ?? null)

async function load() {
  try {
    const [o, a] = await Promise.all([
      apiJson<{ cases: CaseSummary[] }>('/v1/admin/queue?state=open'),
      apiJson<{ cases: CaseSummary[] }>('/v1/admin/queue?state=auto_confirmed'),
    ])
    open.value = o.cases
    auto.value = a.cases
    error.value = ''
  } catch (e) {
    error.value = t('failed', { error: errorText(e) })
  }
  loaded.value = true
}

const brands = computed(() => {
  const counts = new Map<string, number>()
  // Every chip count is over the cases awaiting review, so the numbers add up to "All".
  for (const r of open.value) {
    if (r.brand) counts.set(r.brand, (counts.get(r.brand) ?? 0) + 1)
  }
  return [...counts.entries()].sort((x, y) => y[1] - x[1]).map(([name, count]) => ({ name, count }))
})
// A brand chip whose brand has left the queue would hide every row with nothing to clear it.
watch(brands, (list) => {
  if (chip.value.startsWith('brand:') && !list.some((b) => 'brand:' + b.name === chip.value)) chip.value = 'all'
})
const highCount = computed(() => open.value.filter((r) => isHigh(r.score)).length)

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  return [...open.value, ...auto.value].filter((r) => {
    if (q && !r.domain.toLowerCase().includes(q) && !(r.brand ?? '').toLowerCase().includes(q)) return false
    if (chip.value === 'high') return isHigh(r.score)
    if (chip.value.startsWith('brand:')) return r.brand === chip.value.slice(6)
    return true
  })
})
const visible = computed(() => filtered.value.slice(0, limit.value))

watch([search, chip], () => {
  limit.value = PAGE
})

function select(domain: string) {
  void router.push('/queue/' + encodeURIComponent(domain))
}

function onChanged() {
  void load()
  void refreshStats()
}

const undoError = ref('')
async function undo(domain: string) {
  undoError.value = ''
  try {
    await postJson('/v1/admin/cases/' + encodeURIComponent(domain) + '/undo-auto-confirm', { reviewer: officerName() })
    await load()
    void refreshStats()
  } catch (e) {
    undoError.value = t('failed', { error: errorText(e) })
  }
}

function move(step: 1 | -1) {
  const rows = visible.value
  if (!rows.length) return
  const i = rows.findIndex((r) => r.domain === selected.value)
  let next: number
  if (i < 0) next = step === 1 ? 0 : rows.length - 1
  else next = Math.min(rows.length - 1, Math.max(0, i + step))
  if (i >= 0 && next === i) return
  card.value?.cancelConfirm()
  const domain = rows[next].domain
  select(domain)
  void nextTick(() => {
    const el = document.querySelector(`[data-domain="${CSS.escape(domain)}"]`)
    el?.scrollIntoView?.({ block: 'nearest' })
  })
}

function onKey(e: KeyboardEvent) {
  if (e.ctrlKey || e.metaKey || e.altKey) return
  const el = e.target as HTMLElement | null
  if (el && (['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName) || el.isContentEditable)) return
  const key = e.key.toLowerCase()
  if (key === 'j') move(1)
  else if (key === 'k') move(-1)
  else if (key === 'c') card.value?.armConfirm()
  else if (key === 'enter') {
    if (card.value?.isArmed()) {
      e.preventDefault()
      card.value.commitConfirm()
    }
  } else if (key === 'escape') {
    if (card.value?.isArmed()) card.value.cancelConfirm()
  } else if (key === 'r') {
    e.preventDefault()
    card.value?.focusReject()
  }
}

onMounted(async () => {
  window.addEventListener('keydown', onKey)
  await load()
  await nextTick()
  if (!startedMedian) {
    startedMedian = true
    startMedianLead()
  }
})
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
// The demo works on the first page of the queue so a case opens at once; the full queue comes back when it stops.
// Sample cases go the moment it stops, even while the real queue is still loading.
watch(demoRunning, (running) => {
  if (!running) {
    open.value = []
    auto.value = []
    loaded.value = false
    if (selected.value && isDemoOnly(selected.value)) void router.replace('/queue')
    void refreshStats()
  }
  void load()
})
</script>

<template>
  <div class="page-head">
    <h1>{{ t('navQueue') }}</h1>
  </div>
  <StatStrip />
  <div class="queue-layout">
    <div class="card">
      <div class="card-section">
        <label class="search">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="7" cy="7" r="4.5" /><path d="M10.5 10.5L14 14" /></svg>
          <input v-model="search" type="search" :placeholder="t('searchPlaceholder')" :aria-label="t('searchPlaceholder')" />
        </label>
        <div class="chips">
          <button type="button" class="chip" :class="{ active: chip === 'all' }" :aria-pressed="chip === 'all'" @click="chip = 'all'">
            {{ t('chipAll') }} <span class="count">{{ open.length }}</span>
          </button>
          <button type="button" class="chip" :class="{ active: chip === 'high' }" :aria-pressed="chip === 'high'" @click="chip = 'high'">
            {{ t('chipHighRisk') }} <span class="count">{{ highCount }}</span>
          </button>
          <button
            v-for="b in brands"
            :key="b.name"
            type="button"
            class="chip"
            :class="{ active: chip === 'brand:' + b.name }"
            :aria-pressed="chip === 'brand:' + b.name"
            @click="chip = 'brand:' + b.name"
          >
            {{ b.name }} <span class="count">{{ b.count }}</span>
          </button>
        </div>
      </div>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <p v-if="undoError" class="error" role="alert">{{ undoError }}</p>
      <p v-if="!loaded" class="empty">{{ t('loading') }}</p>
      <div v-else-if="!open.length && !auto.length && !error" class="empty">{{ t('queueEmpty') }}</div>
      <div v-else-if="!filtered.length && !error" class="empty">{{ t('noMatches') }}</div>
      <template v-else>
        <div class="q-head">
          <span>{{ t('colDomain') }}</span>
          <span>{{ t('colRisk') }}</span>
        </div>
        <div
          v-for="row in visible"
          :key="row.domain"
          class="q-row-wrap"
        >
          <button
            type="button"
            class="q-row"
            :class="{ selected: row.domain === selected, dim: row.state === 'auto_confirmed' }"
            :data-domain="row.domain"
            :aria-current="row.domain === selected ? 'true' : undefined"
            @click="select(row.domain)"
          >
            <span class="q-domain">{{ defang(row.domain) }}</span>
            <span v-if="row.state !== 'auto_confirmed'" class="q-score" :class="band(row.score)">{{ row.score }}</span>
            <span v-if="row.state === 'auto_confirmed'" class="q-sub">{{ t('autoConfirmedRow') }}</span>
            <span v-else class="q-sub">
              <bdi>{{ row.brand ? t('impersonates', { brand: row.brand }) : t('noBrand') }}</bdi>
              <template v-if="rowTagText(row)"> · <bdi>{{ rowTagText(row) }}</bdi></template>
            </span>
            <span class="q-age">{{ formatAge(row.first_seen) }}</span>
          </button>
          <button v-if="row.state === 'auto_confirmed'" type="button" class="link undo-btn" @click="undo(row.domain)">
            {{ t('undo') }}
          </button>
        </div>
        <div class="card-section q-foot">
          <span class="muted">{{ t('showingOf', { shown: visible.length, total: filtered.length }) }}</span>
          <button v-if="filtered.length > visible.length" type="button" class="link" @click="limit += PAGE">
            {{ t('loadMore') }}
          </button>
        </div>
      </template>
    </div>
    <CaseCard v-if="selected" ref="card" :domain="selected" @changed="onChanged" />
    <div v-else class="card empty">{{ t('selectCase') }}</div>
  </div>
</template>

<style scoped>
.q-row-wrap {
  position: relative;
}
.q-row-wrap .undo-btn {
  position: absolute;
  inset-inline-end: 12px;
  inset-block-start: 10px;
}
.q-foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.error {
  margin-inline: 12px;
}
</style>
