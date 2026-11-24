<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { adaptRefused } from '../adapt'
import { ApiError, apiJson, download, errorText, postJson } from '../api'
import TakedownDetail from '../components/TakedownDetail.vue'
import { defang } from '../defang'
import { demoRunning } from '../demo'
import { formatTime, t } from '../i18n'
import { officerName } from '../session'
import { statusText } from '../takedown'
import type { CaseSummary, Pack, TakedownRequest, TakedownStats } from '../types'

const confirmed = ref<string[]>([])
const picked = reactive(new Set<string>())
const packs = ref<Pack[]>([])
const built = ref<{ packs: Pack[]; without_recipient: string[]; refused?: { domain: string; reason: string }[] } | null>(null)
const refused = ref<{ domain: string; reason: string }[]>([])
const error = ref('')
const copiedId = ref('')
const requests = ref<TakedownRequest[]>([])
const stats = ref<TakedownStats | null>(null)
const openId = ref('')
const queueLoaded = ref(false)
const packsLoaded = ref(false)

const openCount = computed(() => (stats.value ? stats.value.by_status.sent + stats.value.by_status.offline_pending + stats.value.by_status.reopened : 0))

async function loadPacks() {
  const list = await apiJson<{ packs: Pack[]; requests: TakedownRequest[] }>('/v1/admin/takedowns')
  packs.value = list.packs
  requests.value = list.requests
}

async function loadStats() {
  try {
    stats.value = await apiJson<TakedownStats>('/v1/admin/takedowns/stats')
  } catch {
    stats.value = null
  }
}

async function refreshAfterChange() {
  try {
    await loadPacks()
  } catch (e) {
    error.value = t('failed', { error: errorText(e) })
  }
  await loadStats()
}

async function loadConfirmed() {
  const queue = await apiJson<{ cases: CaseSummary[] }>('/v1/admin/queue?state=all')
  confirmed.value = queue.cases.filter((c) => c.state === 'confirmed').map((c) => c.domain)
}

/** The queue is many pages long, so the requests and figures do not wait for it. */
async function load() {
  const failed = (e: unknown) => {
    error.value = t('failed', { error: errorText(e) })
  }
  await Promise.all([
    loadConfirmed().catch(failed).finally(() => (queueLoaded.value = true)),
    loadPacks().catch(failed).finally(() => (packsLoaded.value = true)),
    loadStats(),
  ])
}

function toggle(domain: string, on: boolean) {
  if (on) picked.add(domain)
  else picked.delete(domain)
}

async function build() {
  built.value = null
  refused.value = []
  error.value = ''
  try {
    built.value = await postJson('/v1/admin/takedowns', { domains: [...picked], generated_by: officerName() })
    refused.value = built.value?.refused ?? []
    picked.clear()
    await refreshAfterChange()
  } catch (e) {
    if (e instanceof ApiError && e.status === 409) {
      refused.value = adaptRefused(e.body)
    } else {
      error.value = t('failed', { error: errorText(e) })
    }
  }
}

async function markSent(id: string) {
  try {
    await postJson(`/v1/admin/takedowns/${id}/sent`, { sent_by: officerName() })
    await refreshAfterChange()
  } catch (e) {
    error.value = t('failed', { error: errorText(e) })
  }
}

async function copy(pack: Pack) {
  try {
    await navigator.clipboard.writeText(pack.recipient)
    copiedId.value = pack.id
  } catch (e) {
    error.value = t('failed', { error: errorText(e) })
  }
}

async function save(pack: Pack) {
  try {
    await download(`/v1/admin/takedowns/${pack.id}/pack.zip`, `${pack.id}.zip`)
  } catch (e) {
    error.value = t('failed', { error: errorText(e) })
  }
}

onMounted(load)
// Sample packs shown during the demo go away as soon as it stops.
watch(demoRunning, (running) => {
  if (running) return
  packs.value = []
  requests.value = []
  stats.value = null
  confirmed.value = []
  openId.value = ''
  queueLoaded.value = false
  packsLoaded.value = false
  void load()
})
</script>

<template>
  <div class="page-head">
    <h1>{{ t('navTakedowns') }}</h1>
  </div>
  <p class="notice">{{ t('takedownNotice') }}</p>
  <p v-if="error" class="error" role="alert">{{ error }}</p>

  <div class="card">
    <div class="card-section">
      <h2 class="section-title">{{ t('pickConfirmed') }}</h2>
    </div>
    <p v-if="!queueLoaded" class="muted card-section" role="status">{{ t('loading') }}</p>
    <p v-else-if="!confirmed.length" class="empty">{{ t('noConfirmed') }}</p>
    <table v-else class="table">
      <thead>
        <tr>
          <th class="sel"></th>
          <th>{{ t('domain') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="domain in confirmed" :key="domain">
          <td class="sel">
            <input
              type="checkbox"
              :id="`pick-${domain}`"
              :checked="picked.has(domain)"
              @change="toggle(domain, ($event.target as HTMLInputElement).checked)"
            />
          </td>
          <td :data-label="t('domain')">
            <label :for="`pick-${domain}`" class="mono">{{ defang(domain) }}</label>
          </td>
        </tr>
      </tbody>
    </table>
    <div class="card-section">
      <button class="btn primary" :disabled="!picked.size" @click="build">{{ t('buildPacks') }}</button>
    </div>

    <div v-if="refused.length" class="card-section error" role="alert">
      <strong>{{ t('refused') }}</strong>
      <ul>
        <li v-for="item in refused" :key="item.domain">
          <span class="mono">{{ defang(item.domain) }}</span>: {{ item.reason }}
        </li>
      </ul>
    </div>
    <div v-if="built?.without_recipient.length" class="card-section notice">
      {{ t('withoutRecipient') }}: <span class="mono">{{ built.without_recipient.map(defang).join(', ') }}</span>
    </div>
  </div>

  <div v-if="stats" class="stat-strip">
    <div class="stat"><span class="num">{{ openCount }}</span> {{ t('tdOpen') }}</div>
    <div class="stat" :class="{ bad: stats.overdue }">
      <span class="num">{{ stats.overdue }}</span> {{ t('tdOverdue', { n: stats.sla_hours }) }}
    </div>
    <div class="stat"><span class="num">{{ stats.by_status.closed }}</span> {{ t('tdOfflineCount') }}</div>
    <div v-if="stats.median_hours_to_offline !== null" class="stat">
      <span class="num">{{ stats.median_hours_to_offline }}</span> {{ t('tdMedian') }}
    </div>
  </div>
  <div v-if="stats?.recipients.length" class="card">
    <div class="card-section">
      <h2 class="section-title">{{ t('tdByRecipient') }}</h2>
    </div>
    <table class="table">
      <thead>
        <tr>
          <th>{{ t('tdRecipientKind') }}</th>
          <th>{{ t('tdRequests') }}</th>
          <th>{{ t('tdOfflineCount') }}</th>
          <th>{{ t('tdMedian') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in stats.recipients" :key="r.kind">
          <td :data-label="t('tdRecipientKind')">{{ r.kind }}</td>
          <td :data-label="t('tdRequests')">{{ r.requests }}</td>
          <td :data-label="t('tdOfflineCount')">{{ r.closed }}</td>
          <td :data-label="t('tdMedian')">{{ r.median_hours ?? '' }}</td>
        </tr>
      </tbody>
    </table>
  </div>

  <div :class="{ split: openId }">
    <div class="card">
      <div class="card-section">
        <h2 class="section-title">{{ t('tdRequests') }}</h2>
        <p class="muted">{{ t('tdNothingSent') }}</p>
      </div>
      <p v-if="!packsLoaded" class="muted card-section" role="status">{{ t('loading') }}</p>
      <p v-else-if="!requests.length" class="empty">{{ t('noPacks') }}</p>
      <table v-else class="table">
        <thead>
          <tr>
            <th>{{ t('domain') }}</th>
            <th>{{ t('tdRecipientKind') }}</th>
            <th>{{ t('state') }}</th>
            <th>{{ t('tdSentAt') }}</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in requests" :key="r.id">
            <td :data-label="t('domain')" class="mono">{{ defang(r.domain) }}</td>
            <td :data-label="t('tdRecipientKind')">{{ r.recipient_kind }}</td>
            <td :data-label="t('state')">
              <span class="status-chip" :class="{ confirmed: r.status === 'closed' }">{{ statusText(r) }}</span>
              <span v-if="r.overdue" class="badge warn">{{ t('tdOverdueBadge') }}</span>
            </td>
            <td :data-label="t('tdSentAt')">{{ r.sent_at ? formatTime(r.sent_at) : '' }}</td>
            <td>
              <button class="btn ghost" :aria-pressed="openId === r.id" @click="openId = r.id">{{ t('details') }}</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <TakedownDetail v-if="openId" :id="openId" @close="openId = ''" @changed="refreshAfterChange" />
  </div>

  <div class="card packs">
    <div class="card-section">
      <h2 class="section-title">{{ t('takedowns') }}</h2>
    </div>
    <p v-if="packsLoaded && !packs.length" class="empty">{{ t('noPacks') }}</p>
    <div v-for="pack in packs" :key="pack.id" class="card-section pack-item">
      <p>
        <strong>{{ pack.recipient_kind }}</strong>
        <span class="muted"> · {{ t('generatedAt') }}: {{ formatTime(pack.generated_at) }}</span>
      </p>
      <p>
        {{ t('recipient') }}: <span class="mono">{{ pack.recipient }}</span>
        <button class="btn ghost" @click="copy(pack)">{{ copiedId === pack.id ? t('copied') : t('copy') }}</button>
      </p>
      <p class="mono">{{ pack.domains.map(defang).join(', ') }}</p>
      <div class="hash">{{ t('packHash') }}: {{ pack.sha256 }}</div>
      <p v-if="pack.sent_at">
        <span class="status-chip confirmed">{{ t('sentBy', { who: pack.sent_by ?? '', when: formatTime(pack.sent_at) }) }}</span>
      </p>
      <p v-else>
        <span class="status-chip rejected">{{ t('notSent') }}</span>
      </p>
      <div class="row-actions">
        <button class="btn" @click="save(pack)">{{ t('downloadPack') }}</button>
        <button v-if="!pack.sent_at" class="btn" @click="markSent(pack.id)">{{ t('markSent') }}</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.card {
  margin-block-end: 16px;
}
.sel {
  inline-size: 40px;
}
.pack-item p {
  margin-block: 0 8px;
}
.row-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-block-start: 8px;
}
</style>
