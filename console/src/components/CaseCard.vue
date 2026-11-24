<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { apiJson, download, errorText, postJson } from '../api'
import { defang } from '../defang'
import { formatAge, formatTime, locale, t, type Key } from '../i18n'
import { officerName } from '../session'
import { leadHours, useStats } from '../stats'
import type { CaseDetail, EvidenceExport, LeadSide } from '../types'
import BlobImage from './BlobImage.vue'

const REJECT_REASONS = [
  'legitimate_site',
  'parked_or_empty',
  'already_offline',
  'not_enough_evidence',
  'test_or_internal',
] as const

const KNOWN_SOURCES = ['sandbox', 'rdap', 'kartoshka'] as const
const KNOWN_FOUND_VIA = ['hunter', 'user_report', 'watchlist', 'officer', 'batch', 'api', 'gatekeeper', 'share', 'paste'] as const

const props = defineProps<{ domain: string }>()
const emit = defineEmits<{ changed: [] }>()

const { chain } = useStats()

const detail = ref<CaseDetail | null>(null)
const evidence = ref<EvidenceExport | null>(null)
const error = ref('')
// The finished action is kept as a key, so the notice follows a language switch.
const noticeWhat = ref<Key | ''>('')
const notice = computed(() => (noticeWhat.value ? t('done', { what: t(noticeWhat.value) }) : ''))
const rejectReason = ref('')
const armed = ref(false)
const busy = ref(false)
const copied = ref(false)
const rejectSelect = ref<HTMLSelectElement | null>(null)

const path = computed(() => `/v1/admin/cases/${encodeURIComponent(props.domain)}`)

const reasonText = (r: { en: string; ar: string }) => (locale.value === 'ar' ? r.ar : r.en)

function sourceLabel(source: string): string {
  return (KNOWN_SOURCES as readonly string[]).includes(source) ? t(`reasonSource_${source}` as Key) : source
}

const statusKey = computed<Key>(() => {
  switch (detail.value?.state) {
    case 'confirmed':
      return 'statusConfirmed'
    case 'rejected':
      return 'statusRejected'
    default:
      return 'statusSuspected'
  }
})
const statusClass = computed(() => {
  const s = detail.value?.state
  return s === 'confirmed' ? 'confirmed' : s === 'rejected' ? 'rejected' : 'suspected'
})

const proxied = computed(() => !!(detail.value?.location?.behind_proxy || detail.value?.infrastructure.proxy))
const hosting = computed(() => (proxied.value ? t('hostingProxy') : (detail.value?.location?.hosted_in ?? t('unknown'))))
const networkOwner = computed(() => {
  const infra = detail.value?.infrastructure
  return infra?.ip_owner ?? infra?.ip_network ?? detail.value?.location?.network_owner ?? null
})

const leadLines = computed(() => {
  const lead = detail.value?.lead_time
  if (leadHours(lead) === null) return []
  const out: string[] = []
  const sides: [LeadSide | null | undefined, Key][] = [
    [lead?.gsb, 'svcGsb'],
    [lead?.vt, 'svcVt'],
  ]
  for (const [side, svc] of sides) {
    if (!side || (side.state !== 'ahead' && side.state !== 'hit') || typeof side.at_least_hours !== 'number') continue
    const service = t(svc)
    const n = side.at_least_hours
    if (side.state === 'ahead') out.push(t('leadAhead', { n, service }))
    else out.push(n > 0 ? t('leadBefore', { n, service }) : t('leadZero', { service }))
  }
  return out
})

const foundVia = computed(() =>
  (detail.value?.sources ?? [])
    .map((s) => ((KNOWN_FOUND_VIA as readonly string[]).includes(s) ? t(`src_${s}` as Key) : s))
    .join(', '),
)

const hasSummary = computed(() => !!(detail.value?.summary && (detail.value.summary.en || detail.value.summary.ar)))

async function load() {
  const requested = path.value
  error.value = ''
  armed.value = false
  evidence.value = null
  try {
    const loaded = await apiJson<CaseDetail>(requested)
    if (requested !== path.value) return
    detail.value = loaded
    if (loaded.evidence_id) {
      try {
        const exported = await apiJson<EvidenceExport>(`/v1/evidence/${loaded.evidence_id}.json`)
        if (requested === path.value) evidence.value = exported
      } catch {
        // The record number and hash are optional.
      }
    }
  } catch (e) {
    if (requested !== path.value) return
    detail.value = null
    error.value = t('failed', { error: errorText(e) })
  }
}

async function save(file: string, filename: string) {
  error.value = ''
  try {
    await download(file, filename)
  } catch (e) {
    error.value = t('failed', { error: errorText(e) })
  }
}

async function act(what: Key, work: () => Promise<unknown>) {
  error.value = ''
  noticeWhat.value = ''
  armed.value = false
  busy.value = true
  try {
    await work()
    noticeWhat.value = what
    await load()
    emit('changed')
  } catch (e) {
    error.value = t('failed', { error: errorText(e) })
  } finally {
    busy.value = false
  }
}

const reviewer = () => ({ reviewer: officerName() })

function review(decision: 'confirm' | 'reject') {
  if (busy.value || !detail.value || detail.value.domain !== props.domain) return
  if (decision === 'confirm' && detail.value.state === 'confirmed') return
  const evidenceId = detail.value.evidence_id
  if (!evidenceId) return
  const reason = decision === 'reject' ? rejectReason.value : null
  void act(decision, () => postJson(`/v1/review/${evidenceId}`, { decision, reason, reviewer: officerName() }))
}

async function copyHash() {
  if (!evidence.value) return
  try {
    await navigator.clipboard?.writeText(evidence.value.hash)
    copied.value = true
    setTimeout(() => (copied.value = false), 1500)
  } catch {
    // Clipboard may be blocked.
  }
}

function armConfirm(): void {
  if (detail.value?.evidence_id && !busy.value && detail.value.state !== 'confirmed') armed.value = true
}
function commitConfirm(): boolean {
  if (!armed.value) return false
  armed.value = false
  review('confirm')
  return true
}
function cancelConfirm(): void {
  armed.value = false
}
function isArmed(): boolean {
  return armed.value
}
function focusReject(): void {
  rejectSelect.value?.focus()
}

defineExpose({ armConfirm, commitConfirm, cancelConfirm, isArmed, focusReject })

watch(
  () => props.domain,
  () => {
    // A different case: drop everything that belonged to the previous one before loading,
    // so no action can reach the old case while the new one is still on its way.
    detail.value = null
    evidence.value = null
    rejectReason.value = ''
    noticeWhat.value = ''
    armed.value = false
    void load()
  },
  { immediate: true },
)
</script>

<template>
  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <p v-if="!detail && !error" class="muted">{{ t('loading') }}</p>
  <article v-if="detail" class="card case-card">
    <section class="card-section case-head">
      <div class="case-head-main">
        <p class="muted">
          {{ detail.brand ? t('impersonates', { brand: detail.brand }) : t('noBrand') }} ·
          {{ t('firstSeenAgo', { age: formatAge(detail.first_seen) }) }}
        </p>
        <h2 class="mono case-domain">{{ defang(detail.domain) }}</h2>
        <p v-if="detail.title" class="case-page-title">
          {{ t('pageTitleLabel') }} <q dir="auto">{{ detail.title }}</q>
        </p>
      </div>
      <div class="case-head-score">
        <p dir="ltr">
          <span class="score-big">{{ detail.score }}</span> <span class="score-out">{{ t('scoreOutOf') }}</span>
        </p>
        <span :class="['status-chip', statusClass]">
          {{ t(statusKey) }}<template v-if="detail.state === 'auto_confirmed'"> · {{ t('statusAutoNote') }}</template>
        </span>
      </div>
    </section>

    <section class="card-section">
      <p v-if="!detail.reasons.length" class="muted">{{ t('noReasons') }}</p>
      <template v-else>
        <p class="muted">{{ detail.reasons.length === 1 ? t('scoredOnOne') : t('scoredOn', { n: detail.reasons.length }) }}</p>
        <ul class="reason-list">
          <li v-for="reason in detail.reasons" :key="reason.code">
            <span class="mono reason-weight">+{{ reason.weight }}</span>
            <span class="reason-text" :lang="locale" :dir="locale === 'ar' ? 'rtl' : 'ltr'">{{ reasonText(reason) }}</span>
            <span class="muted reason-source">{{ t('reasonSourceLabel', { source: sourceLabel(reason.source) }) }}</span>
          </li>
        </ul>
      </template>
    </section>

    <section class="card-section">
      <div class="action-row">
        <button
          type="button"
          :class="['btn', 'primary', { armed }]"
          :disabled="!detail.evidence_id || busy || detail.state === 'confirmed'"
          @click="review('confirm')"
        >
          <template v-if="armed">{{ t('confirmArmed') }}</template>
          <template v-else>{{ t('confirmAndBlocklist') }} <span class="kbd">C</span></template>
        </button>
        <select ref="rejectSelect" v-model="rejectReason" :aria-label="t('rejectReason')" :disabled="!detail.evidence_id">
          <option value="">{{ t('chooseReason') }}</option>
          <option v-for="code in REJECT_REASONS" :key="code" :value="code">{{ t(`reason_${code}`) }}</option>
        </select>
        <button type="button" class="btn danger" :disabled="!detail.evidence_id || !rejectReason || busy" @click="review('reject')">
          {{ t('rejectEllipsis') }} <span class="kbd">R</span>
        </button>
      </div>
      <div class="action-row">
        <button type="button" class="btn ghost" @click="act('recheck', () => postJson(`${path}/recheck`, reviewer()))">
          {{ t('rerunChecks') }}
        </button>
        <button type="button" class="btn ghost" @click="act('watch', () => postJson(`${path}/watch`, reviewer()))">
          {{ t('addToWatchlist') }}
        </button>
        <button
          v-if="detail.state === 'auto_confirmed'"
          type="button"
          class="btn ghost"
          @click="act('undoAuto', () => postJson(`${path}/undo-auto-confirm`, reviewer()))"
        >
          {{ t('undoAuto') }}
        </button>
        <RouterLink class="link" to="/chain">{{ t('viewChain') }}</RouterLink>
      </div>
      <p v-if="notice" class="notice" role="status">{{ notice }}</p>
    </section>

    <section v-if="hasSummary" class="card-section">
      <div class="section-head">
        <h3 class="section-title">{{ t('summaryTitle') }}</h3>
        <span class="muted">{{ t('machineGenerated') }}</span>
      </div>
      <div class="bilingual">
        <p lang="en" dir="ltr">{{ detail.summary?.en }}</p>
        <p lang="ar" dir="rtl">{{ detail.summary?.ar }}</p>
      </div>
    </section>

    <section class="card-section">
      <h3 class="section-title">{{ t('infrastructure') }}</h3>
      <dl class="kv">
        <dt>{{ t('hosting') }}</dt>
        <dd>{{ hosting }}</dd>
        <template v-if="networkOwner">
          <dt>{{ t('network') }}</dt>
          <dd>{{ networkOwner }}</dd>
        </template>
        <template v-if="detail.infrastructure.ip">
          <dt>{{ t('ip') }}</dt>
          <dd class="mono">{{ defang(detail.infrastructure.ip) }}</dd>
        </template>
        <template v-if="detail.infrastructure.registrar">
          <dt>{{ t('registrar') }}</dt>
          <dd>{{ detail.infrastructure.registrar }}</dd>
        </template>
        <template v-if="detail.infrastructure.registered_at">
          <dt>{{ t('registered') }}</dt>
          <dd>{{ formatTime(detail.infrastructure.registered_at) }}</dd>
        </template>
        <template v-if="detail.infrastructure.name_servers?.length">
          <dt>{{ t('nameServers') }}</dt>
          <dd class="mono">{{ detail.infrastructure.name_servers.map(defang).join(', ') }}</dd>
        </template>
        <template v-if="leadLines.length">
          <dt>{{ t('leadTimeLabel') }}</dt>
          <dd>
            <span v-for="line in leadLines" :key="line" class="lead-line">{{ line }}</span>
          </dd>
        </template>
        <template v-if="foundVia">
          <dt>{{ t('foundVia') }}</dt>
          <dd>{{ foundVia }}</dd>
        </template>
      </dl>
    </section>

    <section class="card-section">
      <div class="section-head">
        <h3 class="section-title">{{ t('evidenceTitle') }}</h3>
        <span class="muted">
          <template v-if="chain">{{ chain.intact ? t('chainIntactShort') : t('chainBrokenShort') }}</template>
          <template v-if="chain && evidence"> · </template>
          <template v-if="evidence">{{ t('chainRecord', { n: evidence.seq }) }}</template>
        </span>
      </div>
      <div v-if="detail.has_screenshot && detail.evidence_id" class="shot">
        <BlobImage :path="`/v1/admin/evidence/${detail.evidence_id}/screenshot.png`" />
      </div>
      <p v-else class="muted">{{ t('noScreenshot') }}</p>
      <p v-if="evidence" class="hash">
        {{ t('sha256') }} <span class="mono">{{ evidence.hash }}</span>
        <button type="button" class="btn ghost" @click="copyHash">{{ copied ? t('copied') : t('copy') }}</button>
      </p>
      <div v-if="detail.evidence_id" class="action-row">
        <button
          type="button"
          class="btn ghost"
          @click="save(`/v1/evidence/${detail.evidence_id}.pdf`, `evidence-${detail.evidence_id}.pdf`)"
        >
          {{ t('downloadPdf') }}
        </button>
        <button
          type="button"
          class="btn ghost"
          @click="save(`/v1/evidence/${detail.evidence_id}.json`, `evidence-${detail.evidence_id}.json`)"
        >
          {{ t('downloadJson') }}
        </button>
      </div>
      <p v-else class="muted">{{ t('noEvidence') }}</p>
    </section>

    <section class="card-section">
      <div class="section-head">
        <h3 class="section-title">{{ t('reportsTitle') }}</h3>
        <span>{{ detail.reports }}</span>
      </div>
      <p class="muted">{{ t('reportsNotInScore') }}</p>
      <ul v-if="detail.reports > 0 && detail.report_notes.length" class="notes">
        <li v-for="note in detail.report_notes" :key="note.id">
          <q dir="auto">{{ note.note }}</q>
          <div class="muted">{{ formatTime(note.created_at) }}</div>
        </li>
      </ul>
      <p v-else-if="detail.reports === 0" class="muted">{{ t('noReports') }}</p>
    </section>

    <section class="card-section">
      <h3 class="section-title">{{ t('campaign') }}</h3>
      <RouterLink v-if="detail.campaign_id" class="link" :to="`/campaigns/${detail.campaign_id}`">{{ t('openCampaign') }}</RouterLink>
      <p v-else class="muted">{{ t('noCampaign') }}</p>
    </section>

    <section class="card-section">
      <h3 class="section-title">{{ t('pastReviews') }}</h3>
      <ul v-if="detail.reviews.length">
        <li v-for="past in detail.reviews" :key="past.id">
          {{ past.decision }}{{ past.reason ? ` (${past.reason})` : '' }} · {{ past.reviewer }} · {{ formatTime(past.reviewed_at) }}
        </li>
      </ul>
      <p v-else class="muted">{{ t('noReviews') }}</p>
    </section>
  </article>
</template>

<style scoped>
.case-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}
.case-head-score {
  text-align: end;
}
.case-domain {
  font-size: 22px;
  margin-block: 4px;
  overflow-wrap: anywhere;
}
.section-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
}
.reason-list,
.notes {
  list-style: none;
  padding: 0;
  margin-block: 8px 0;
}
.reason-list li {
  display: flex;
  gap: 10px;
  align-items: baseline;
  padding-block: 4px;
}
.reason-text {
  flex: 1;
}
.action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-block-start: 8px;
}
.lead-line {
  display: block;
}
.hash .btn {
  margin-inline-start: 8px;
}
</style>
