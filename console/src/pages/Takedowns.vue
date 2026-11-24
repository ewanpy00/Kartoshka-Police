<script setup lang="ts">
// Takedown tracker (D5). Nothing is sent from here: "Send" opens the mail client (or the recipient's
// form) and downloads the pack; the officer then presses "Mark as sent".
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { download, get, onEvent, post } from '../api'
import DefangedDomain from '../components/DefangedDomain.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { t } from '../i18n'
import type { MessageKey } from '../i18n/en'
import { reviewer } from '../session'
import type { Takedown, TakedownStats } from '../types'

const COLUMNS = ['pack_ready', 'sent', 'offline_pending', 'closed', 'reopened'] as const
const rows = ref<Takedown[]>([])
const stats = ref<TakedownStats | null>(null)
const open = ref<(Takedown & { pack: Takedown[] }) | null>(null)
const domains = ref('')
const error = ref('')
const notice = ref('')
const busy = ref(false)
const recipient = ref('')

async function load() {
  error.value = ''
  try {
    const page = await get<{ requests: Takedown[] }>('/v1/admin/takedowns', { recipient: recipient.value })
    rows.value = page.requests
    stats.value = await get<TakedownStats>('/v1/admin/takedowns/stats')
    if (open.value) await show(open.value.id)
  } catch (e) {
    error.value = (e as Error).message
  }
}

const board = computed(() => Object.fromEntries(COLUMNS.map((c) => [c, rows.value.filter((r) => r.status === c)])))

async function show(id: string) {
  open.value = await get(`/v1/admin/takedowns/${encodeURIComponent(id)}`)
}

async function run(fn: () => Promise<string>) {
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    notice.value = await fn()
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = false
  }
}

function create() {
  const list = domains.value.split(/[\s,]+/).map((d) => d.trim().toLowerCase().replace(/\[\.\]/g, '.')).filter(Boolean)
  if (!list.length) return
  run(async () => {
    const result = await post<{ requests: Takedown[]; refused: { display: string; why: string }[] }>(
      '/v1/admin/takedowns', { domains: list, reviewer: reviewer() })
    domains.value = ''
    await load()
    const refused = result.refused.map((r) => `${r.display}: ${r.why}`).join('; ')
    return `${result.requests.length} request(s) prepared.${refused ? ` Refused: ${refused}.` : ''}`
  })
}

function send(request: Takedown) {
  run(async () => {
    const headers = await download(`/v1/admin/takedowns/${encodeURIComponent(request.id)}/pack.zip`, `${request.id}.zip`)
    if (request.form) {
      window.open(request.recipient, '_blank', 'noopener')
    } else {
      const names = (open.value?.pack ?? [request]).map((r) => r.display).join(', ')
      const subject = encodeURIComponent(`Phishing takedown request: ${names}`)
      const body = encodeURIComponent('Please find the evidence pack attached (email.txt in the zip has the full text in Arabic and English).')
      window.location.href = `mailto:${request.recipient}?subject=${subject}&body=${body}`
    }
    return headers['x-pack-matches'] === 'true'
      ? 'Pack downloaded; its SHA-256 matches the stored one. Attach it, send, then mark as sent.'
      : 'Pack downloaded, but its hash differs from the stored one: check before sending.'
  })
}

function markSent(request: Takedown) {
  run(async () => {
    await post(`/v1/admin/takedowns/${encodeURIComponent(request.id)}/sent`, { reviewer: reviewer() })
    await load()
    return 'Marked as sent. Re-checks have started.'
  })
}

function checkNow(request: Takedown) {
  run(async () => {
    await post(`/v1/admin/takedowns/${encodeURIComponent(request.id)}/recheck`)
    setTimeout(load, 20_000)
    return 'Check queued (both sandbox profiles). The card updates when it finishes.'
  })
}

let stop: (() => void) | undefined
onMounted(() => {
  load()
  stop = onEvent((event) => {
    if (event.type === 'takedown.offline') load()
  })
})
onUnmounted(() => stop?.())
</script>

<template>
  <main class="page">
    <div class="row">
      <h1>{{ t('takedowns.title') }}</h1>
      <span class="spacer" />
      <select v-model="recipient" @change="load"><option value="">all recipients</option>
        <option v-for="r in ['registrar', 'hosting', 'cloudflare', 'aeda', 'gsb']" :key="r" :value="r">{{ r }}</option></select>
      <button @click="load">{{ t('common.refresh') }}</button>
    </div>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="notice" class="notice">{{ notice }}</p>
    <div v-if="stats" class="grid cols-4">
      <div class="card"><div class="muted small">open</div><div class="stat">{{ (stats.by_status.sent ?? 0) + (stats.by_status.offline_pending ?? 0) + (stats.by_status.reopened ?? 0) }}</div></div>
      <div class="card"><div class="muted small">overdue (&gt; {{ stats.sla_hours }} h)</div><div class="stat">{{ stats.overdue }}</div></div>
      <div class="card"><div class="muted small">closed</div><div class="stat">{{ stats.by_status.closed ?? 0 }}</div></div>
      <div class="card"><div class="muted small">median hours to offline</div><div class="stat">{{ stats.median_hours_to_offline ?? '—' }}</div></div>
    </div>
    <div class="card new">
      <h2>{{ t('takedowns.new') }}</h2>
      <div class="row">
        <input v-model="domains" class="grow" placeholder="officer-confirmed domains, separated by spaces or commas" @keyup.enter="create" />
        <button class="primary" :disabled="busy || !domains" @click="create">{{ t('takedowns.new') }}</button>
      </div>
      <p class="muted small">One request per recipient (registrar, host or Cloudflare, aeDA for .ae, Google Safe Browsing); one pack per recipient.</p>
    </div>
    <div class="board">
      <div v-for="column in COLUMNS" :key="column" class="column">
        <h3>{{ t(`status.${column}` as MessageKey) }} ({{ board[column].length }})</h3>
        <div v-for="r in board[column]" :key="r.id" class="card item" @click="show(r.id)">
          <DefangedDomain :display="r.display" />
          <div class="small muted">{{ r.recipient_kind }}<template v-if="r.offline_reason"> · {{ r.offline_reason }}</template></div>
          <span v-if="r.overdue" class="badge overdue">overdue</span>
        </div>
      </div>
    </div>
    <aside v-if="open" class="drawer">
      <div class="row"><h2><DefangedDomain :display="open.display" /></h2><span class="spacer" /><button class="ghost" @click="open = null">✕</button></div>
      <StatusBadge :value="open.status" /> <span v-if="open.overdue" class="badge overdue">overdue</span>
      <dl class="kv small">
        <dt>recipient</dt><dd>{{ open.recipient_kind }} · {{ open.recipient }}</dd>
        <dt>pack SHA-256</dt><dd class="mono">{{ open.pack_sha256 }}</dd>
        <dt>prepared</dt><dd>{{ new Date(open.generated_at).toLocaleString() }}</dd>
        <dt>sent</dt><dd>{{ open.sent_at ? `${new Date(open.sent_at).toLocaleString()} by ${open.sent_by}` : '—' }}</dd>
        <dt>offline</dt><dd>{{ open.offline_at ? `${new Date(open.offline_at).toLocaleString()} · ${open.offline_reason} · ${open.checks_offline} check(s)` : '—' }}</dd>
        <dt>campaign</dt><dd><RouterLink v-if="open.campaign_id" :to="{ name: 'campaign', params: { id: open.campaign_id } }">{{ open.campaign_id }}</RouterLink><template v-else>—</template></dd>
      </dl>
      <h3>In this pack</h3>
      <ul class="small"><li v-for="m in open.pack" :key="m.id"><DefangedDomain :display="m.display" /> · {{ m.status }}</li></ul>
      <div class="row">
        <button :disabled="busy" @click="send(open)">{{ t('takedowns.send') }}</button>
        <button class="primary" :disabled="busy || open.status !== 'pack_ready'" @click="markSent(open)">{{ t('takedowns.sent') }}</button>
        <button :disabled="busy || open.status === 'pack_ready'" @click="checkNow(open)">{{ t('takedowns.check') }}</button>
      </div>
      <p class="muted small">Offline counts only when the phone and the bot profile both find the site gone, in checks at least one re-check interval apart.</p>
    </aside>
  </main>
</template>

<style scoped>
.new { margin: 1rem 0; }
.grow { flex: 1; min-width: 16rem; }
.board { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 0.75rem; }
@media (max-width: 1000px) { .board { grid-template-columns: minmax(0, 1fr); } }
.column h3 { margin-bottom: 0.5rem; }
.item { cursor: pointer; padding: 0.5rem 0.6rem; }
.item + .item { margin-top: 0.5rem; }
</style>
