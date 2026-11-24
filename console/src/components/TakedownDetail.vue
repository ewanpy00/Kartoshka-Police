<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { apiJson, errorText, postJson } from '../api'
import { defang } from '../defang'
import { formatTime, t } from '../i18n'
import { canCheck, OFFLINE_CHECKS_NEEDED, statusText, translateIfKnown } from '../takedown'
import type { AuditEntry, TakedownDetail, TakedownStatus } from '../types'

const props = defineProps<{ id: string }>()
const emit = defineEmits<{ close: []; changed: [] }>()

const POLL_MS = 5000
const GIVE_UP_MS = 60000
const STATUSES: readonly TakedownStatus[] = ['pack_ready', 'sent', 'offline_pending', 'closed', 'reopened']

const detail = ref<TakedownDetail | null>(null)
const entries = ref<AuditEntry[]>([])
const loading = ref(true)
const error = ref('')
const checking = ref(false)
const queued = ref(false)
let pollTimer: ReturnType<typeof setInterval> | undefined
let giveUpTimer: ReturnType<typeof setTimeout> | undefined
let seq = 0

const timeline = computed(() => [...entries.value].sort((a, b) => a.created_at.localeCompare(b.created_at) || a.id - b.id))
const others = computed(() => (detail.value?.pack ?? []).filter((r) => r.id !== detail.value?.id))
const reason = computed(() => {
  const raw = detail.value?.offline_reason
  if (!raw) return null
  return translateIfKnown(`offReason_${raw}`) ?? raw
})

function actionText(action: string): string {
  return translateIfKnown(`audit.${action}`) ?? action
}

function newState(entry: AuditEntry): string | null {
  if (entry.action !== 'takedown.state' || !entry.after) return null
  const status = STATUSES.find((s) => s === entry.after?.status)
  const checks = Number(entry.after.checks_offline)
  return statusText({ status: status ?? 'unknown', checks_offline: Number.isFinite(checks) ? checks : 0 })
}

async function fetchAll(): Promise<void> {
  const [d, a] = await Promise.all([
    apiJson<TakedownDetail>('/v1/admin/takedowns/' + encodeURIComponent(props.id)),
    apiJson<{ entries: AuditEntry[] }>('/v1/admin/audit?target=' + encodeURIComponent(props.id) + '&limit=50'),
  ])
  detail.value = d
  entries.value = a.entries
}

function stopChecking(): void {
  clearInterval(pollTimer)
  clearTimeout(giveUpTimer)
  pollTimer = undefined
  giveUpTimer = undefined
  checking.value = false
}

async function load(): Promise<void> {
  stopChecking()
  const mine = ++seq
  detail.value = null
  entries.value = []
  queued.value = false
  error.value = ''
  loading.value = true
  try {
    await fetchAll()
  } catch (e) {
    if (mine === seq) error.value = t('failed', { error: errorText(e) })
  } finally {
    if (mine === seq) loading.value = false
  }
}

async function poll(before: { status: string; checks: number; count: number }, mine: number): Promise<void> {
  try {
    await fetchAll()
  } catch (e) {
    if (mine === seq) error.value = t('failed', { error: errorText(e) })
    return
  }
  if (mine !== seq || !detail.value) return
  if (detail.value.status !== before.status || detail.value.checks_offline !== before.checks || entries.value.length > before.count) {
    stopChecking()
    emit('changed')
  }
}

async function checkNow(): Promise<void> {
  if (!detail.value) return
  const mine = seq
  const before = { status: detail.value.status, checks: detail.value.checks_offline, count: entries.value.length }
  error.value = ''
  checking.value = true
  try {
    await postJson('/v1/admin/takedowns/' + encodeURIComponent(props.id) + '/recheck', {})
  } catch (e) {
    checking.value = false
    error.value = t('failed', { error: errorText(e) })
    return
  }
  queued.value = true
  pollTimer = setInterval(() => void poll(before, mine), POLL_MS)
  giveUpTimer = setTimeout(stopChecking, GIVE_UP_MS)
}

watch(() => props.id, load, { immediate: true })
onBeforeUnmount(() => {
  seq++
  stopChecking()
})
</script>

<template>
  <section class="card td-detail" :aria-label="t('tdDetail')">
    <div class="card-section td-head">
      <h2 class="section-title">{{ t('tdDetail') }}</h2>
      <button class="btn ghost" @click="emit('close')">{{ t('close') }}</button>
    </div>
    <p v-if="loading" class="muted card-section" role="status">{{ t('loading') }}</p>
    <p v-if="error" class="error card-section" role="alert">{{ error }}</p>
    <template v-if="detail">
      <div class="card-section">
        <p class="mono td-domain">{{ defang(detail.domain) }}</p>
        <dl class="kv">
          <dt>{{ t('state') }}</dt>
          <dd>{{ statusText(detail) }}</dd>
          <dt>{{ t('tdRecipientKind') }}</dt>
          <dd>{{ detail.recipient_kind }}</dd>
          <dt>{{ t('recipient') }}</dt>
          <dd>{{ detail.recipient }}</dd>
          <dt>{{ t('packHash') }}</dt>
          <dd class="mono">{{ detail.pack_sha256 }}</dd>
          <dt>{{ t('tdPrepared') }}</dt>
          <dd>{{ formatTime(detail.generated_at) }}</dd>
          <template v-if="detail.sent_at">
            <dt>{{ t('tdSentAt') }}</dt>
            <dd>{{ formatTime(detail.sent_at) }}</dd>
          </template>
          <template v-if="detail.sent_by">
            <dt>{{ t('tdSentBy') }}</dt>
            <dd>{{ detail.sent_by }}</dd>
          </template>
          <template v-if="detail.offline_at">
            <dt>{{ t('tdOfflineSince') }}</dt>
            <dd>{{ formatTime(detail.offline_at) }}</dd>
          </template>
          <template v-if="reason">
            <dt>{{ t('tdOfflineReason') }}</dt>
            <dd>{{ reason }}</dd>
          </template>
          <template v-if="detail.campaign_id">
            <dt>{{ t('campaign') }}</dt>
            <dd>
              <RouterLink class="link mono" :to="`/campaigns/${encodeURIComponent(detail.campaign_id)}`">{{ detail.campaign_id }}</RouterLink>
            </dd>
          </template>
        </dl>
      </div>
      <div v-if="others.length" class="card-section">
        <h3 class="section-title">{{ t('tdInPack') }}</h3>
        <ul class="td-list">
          <li v-for="r in others" :key="r.id">
            <span class="mono">{{ defang(r.domain) }}</span>
            <span class="status-chip">{{ statusText(r) }}</span>
          </li>
        </ul>
      </div>
      <p class="notice card-section">{{ t('tdTwoCheckNote', { total: OFFLINE_CHECKS_NEEDED }) }}</p>
      <div class="card-section">
        <button class="btn primary" :disabled="checking || !canCheck(detail)" @click="checkNow">
          {{ checking ? t('tdChecking') : t('tdCheckNow') }}
        </button>
        <p v-if="!canCheck(detail)" class="muted">{{ t('tdCheckNotSent') }}</p>
        <p v-if="queued" class="notice" role="status">{{ t('tdCheckQueued') }}</p>
      </div>
      <div class="card-section">
        <h3 class="section-title">{{ t('tdTimeline') }}</h3>
        <p v-if="!timeline.length" class="empty">{{ t('tdTimelineEmpty') }}</p>
        <ul v-else class="td-list">
          <li v-for="e in timeline" :key="e.id">
            <span class="muted">{{ formatTime(e.created_at) }}</span>
            <span>{{ actionText(e.action) }}</span>
            <span v-if="newState(e)" class="status-chip">{{ newState(e) }}</span>
          </li>
        </ul>
      </div>
    </template>
  </section>
</template>

<style scoped>
.td-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}
.td-domain {
  margin-block: 0 var(--space-2);
  overflow-wrap: anywhere;
}
.td-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: var(--space-2);
}
.td-list li {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
}
</style>
