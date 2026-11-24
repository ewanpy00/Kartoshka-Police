<script setup lang="ts">
// Live Hunter feed (D1): candidates as they arrive over the WebSocket, the watchlist, and the chain check.
import { onMounted, onUnmounted, ref } from 'vue'
import { get, onEvent } from '../api'
import DefangedDomain from '../components/DefangedDomain.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { t } from '../i18n'
import type { FeedRow, WatchRow } from '../types'

const feed = ref<FeedRow[]>([])
const nextCursor = ref<number | null>(null)
const watch = ref<WatchRow[]>([])
const watchTotal = ref(0)
const source = ref('')
const live = ref(false)
const error = ref('')
const chain = ref<{ ok: boolean; rows: number; broken_at: number | null; checked_at: string } | null>(null)
const spikes = ref<{ brand_id: string; count: number }[]>([])

function defang(value: string): string {
  return value.replace(/^https:\/\//, 'hxxps://').replace(/^http:\/\//, 'hxxp://').replace(/\./g, '[.]')
}

async function load(more = false) {
  error.value = ''
  try {
    const page = await get<{ entries: FeedRow[]; next_cursor: number | null }>('/v1/admin/hunter/feed', {
      source: source.value, cursor: more ? nextCursor.value : undefined,
    })
    feed.value = more ? [...feed.value, ...page.entries] : page.entries
    nextCursor.value = page.next_cursor
    const watched = await get<{ total: number; entries: WatchRow[] }>('/v1/admin/watchlist')
    watch.value = watched.entries
    watchTotal.value = watched.total
  } catch (e) {
    error.value = (e as Error).message
  }
}

async function verify() {
  chain.value = null
  try {
    chain.value = await get('/v1/admin/evidence/verify')
  } catch (e) {
    error.value = (e as Error).message
  }
}

let stop: (() => void) | undefined
onMounted(() => {
  load()
  stop = onEvent((event) => {
    if (event.type === 'hello') live.value = true
    if (event.type === 'hunter.candidate' && (!source.value || event.source === source.value)) {
      const domain = String(event.domain ?? '')
      feed.value.unshift({
        id: Date.now(), source: String(event.source ?? ''), domain, display: defang(domain), display_url: defang(String(event.url ?? domain)),
        brand_id: (event.brand_id as string) ?? null, detail: null, first_seen: String(event.first_seen ?? new Date().toISOString()),
        verdict: null, score: null, stage: null,
      })
      feed.value = feed.value.slice(0, 300)
    }
    if (event.type === 'check.verdict') {
      const row = feed.value.find((r) => r.domain === event.domain)
      if (row) {
        row.verdict = String(event.verdict)
        row.score = Number(event.score)
      }
    }
    if (event.type === 'brand.spike') spikes.value.unshift({ brand_id: String(event.brand_id), count: Number(event.count) })
  })
})
onUnmounted(() => stop?.())
</script>

<template>
  <main class="page">
    <div class="row">
      <h1>{{ t('hunter.title') }}</h1>
      <span class="badge" :class="live ? 'allow' : ''">{{ live ? t('hunter.live') : 'offline' }}</span>
      <select v-model="source" @change="load()"><option value="">{{ t('filter.all') }}</option>
        <option v-for="s in ['ct', 'nrd', 'feed', 'sweep']" :key="s" :value="s">{{ s }}</option></select>
      <span class="spacer" />
      <button @click="verify">{{ t('hunter.chain') }}</button>
    </div>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="chain" :class="chain.ok ? 'notice' : 'error'">
      Evidence chain {{ chain.ok ? 'ok' : 'BROKEN' }} · {{ chain.rows }} records · {{ new Date(chain.checked_at).toLocaleTimeString() }}
      <template v-if="!chain.ok"> · broken at {{ chain.broken_at }}</template>
    </p>
    <p v-for="s in spikes" :key="s.brand_id + s.count" class="error">Spike: {{ s.count }} new candidates for {{ s.brand_id }} in the last hour</p>
    <div class="grid cols-2">
      <div class="card scroll">
        <table>
          <tr><th>first seen</th><th>source</th><th>domain</th><th>brand</th><th>verdict</th></tr>
          <tr v-for="row in feed" :key="row.id" class="clickable" @click="$router.push({ name: 'case', params: { domain: row.domain } })">
            <td class="small">{{ new Date(row.first_seen).toLocaleString() }}</td>
            <td>{{ row.source }}</td>
            <td><DefangedDomain :display="row.display" /></td>
            <td>{{ row.brand_id ?? '—' }}</td>
            <td><StatusBadge v-if="row.verdict" :value="row.verdict" :score="row.score" /></td>
          </tr>
        </table>
        <button v-if="nextCursor" @click="load(true)">{{ t('common.more') }}</button>
      </div>
      <div class="card scroll">
        <h2>{{ t('hunter.watchlist') }} <span class="muted small">({{ watchTotal }})</span></h2>
        <table>
          <tr><th>domain</th><th>reason</th><th>last</th><th>next check</th></tr>
          <tr v-for="row in watch" :key="row.domain" class="clickable" @click="$router.push({ name: 'case', params: { domain: row.domain } })">
            <td><DefangedDomain :display="row.display" /></td>
            <td class="small">{{ row.reason }}</td>
            <td class="small">{{ row.last_status ?? '—' }}</td>
            <td class="small">{{ new Date(row.next_check_at).toLocaleString() }}</td>
          </tr>
        </table>
      </div>
    </div>
  </main>
</template>
