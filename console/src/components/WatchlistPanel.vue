<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { apiJson, errorText } from '../api'
import { defang } from '../defang'
import { formatTime, t } from '../i18n'
import type { Key } from '../i18n'
import type { CaseDetail, WatchRow, Watchlist } from '../types'

const props = defineProps<{ woke: string[] }>()

const PAGE = 50
const MAX_LOOKUPS = 20
const CONCURRENCY = 4
const STATE_KEYS = ['parked', 'unreachable', 'live', 'takedown']
const REASON_KEYS = ['nxdomain', 'servfail', 'rdap_hold', 'http_gone', 'cf_interstitial', 'form_removed', 'refused', 'unreadable']

const list = ref<Watchlist | null>(null)
const error = ref('')
const loaded = ref(false)
const limit = ref(PAGE)
const credential = ref<string[]>([])
const looked = new Set<string>()

function stateText(status: string): string {
  const s = status.toLowerCase()
  if (STATE_KEYS.includes(s)) return t(`watchState_${s}` as Key)
  if (REASON_KEYS.includes(s)) return t(`offReason_${s}` as Key)
  return status
}

function nextText(iso: string | null): string {
  if (!iso) return ''
  const at = Date.parse(iso)
  return Number.isNaN(at) || at < Date.now() ? t('watchDue') : formatTime(iso)
}

async function lookup(rows: WatchRow[]) {
  const targets = rows
    .filter((r) => r.last_status.toLowerCase() === 'live' && !looked.has(r.domain))
    .slice(0, Math.max(0, MAX_LOOKUPS - looked.size))
    .map((r) => r.domain)
  targets.forEach((d) => looked.add(d))
  let next = 0
  const worker = async () => {
    while (next < targets.length) {
      const domain = targets[next++]
      try {
        const detail = await apiJson<CaseDetail>('/v1/admin/cases/' + encodeURIComponent(domain))
        if (detail.asks_for?.length && !credential.value.includes(domain)) credential.value = [...credential.value, domain]
      } catch {
        // A failed single lookup is ignored.
      }
    }
  }
  await Promise.all(Array.from({ length: CONCURRENCY }, worker))
}

async function load() {
  try {
    list.value = await apiJson<Watchlist>('/v1/admin/watchlist')
    error.value = ''
  } catch (e) {
    error.value = t('failed', { error: errorText(e) })
  }
  loaded.value = true
  if (list.value) void lookup(list.value.rows)
}

function flagged(domain: string): boolean {
  return credential.value.includes(domain) || props.woke.includes(domain)
}

const sorted = computed(() => {
  const rows = [...(list.value?.rows ?? [])]
  const time = (r: WatchRow) => (r.next_check_at ? Date.parse(r.next_check_at) : Infinity)
  return rows.sort((a, b) => Number(flagged(b.domain)) - Number(flagged(a.domain)) || time(a) - time(b))
})
const visible = computed(() => sorted.value.slice(0, limit.value))

watch(
  () => props.woke,
  (domains) => {
    const rows = list.value?.rows ?? []
    if (domains.some((d) => !rows.some((r) => r.domain === d))) void load()
  },
  { deep: true },
)

onMounted(load)
</script>

<template>
  <div>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-else-if="!loaded" class="muted" role="status">{{ t('loading') }}</p>
    <div v-else-if="list" class="card">
      <div class="card-section">
        <h2 class="section-title">{{ t('watchTitle') }} <span class="muted">{{ t('watchCount', { n: list.total }) }}</span></h2>
      </div>
      <p v-if="!list.rows.length" class="empty">{{ t('watchEmpty') }}</p>
      <template v-else>
        <div v-for="row in visible" :key="row.domain" class="q-row" :data-domain="row.domain">
          <span class="q-domain">
            <RouterLink :to="'/queue/' + encodeURIComponent(row.domain)">{{ defang(row.domain) }}</RouterLink>
          </span>
          <span class="q-sub">
            <span class="badge block" v-if="flagged(row.domain)">{{ t('watchCredentialForm') }}</span>
            <span>{{ t('watchColAttempts') }}: {{ row.checks_done }}</span>
            <span>{{ t('watchColState') }}: <bdi>{{ stateText(row.last_status) }}</bdi></span>
            <span v-if="row.next_check_at">{{ t('watchColNext') }}: {{ nextText(row.next_check_at) }}</span>
          </span>
        </div>
        <div class="card-section">
          <span class="muted">{{ t('showingOf', { shown: visible.length, total: sorted.length }) }}</span>
          {{ ' ' }}
          <button v-if="sorted.length > visible.length" type="button" class="link" @click="limit += PAGE">
            {{ t('loadMore') }}
          </button>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.q-row {
  cursor: default;
}

.q-row:hover {
  background: transparent;
}

.q-sub {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1) var(--space-3);
}
</style>
