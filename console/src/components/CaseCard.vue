<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { apiJson, download, postJson } from '../api'
import { defang } from '../defang'
import { formatTime, t, type Key } from '../i18n'
import { officerName } from '../session'
import type { CaseDetail } from '../types'
import BlobImage from './BlobImage.vue'
import CaseTitle from './CaseTitle.vue'
import LocationLines from './LocationLines.vue'

const REJECT_REASONS = [
  'legitimate_site',
  'parked_or_empty',
  'already_offline',
  'not_enough_evidence',
  'test_or_internal',
] as const

const props = defineProps<{ domain: string }>()
const emit = defineEmits<{ changed: [] }>()

const detail = ref<CaseDetail | null>(null)
const error = ref('')
const notice = ref('')
const rejectReason = ref('')

const path = computed(() => `/v1/admin/cases/${encodeURIComponent(props.domain)}`)
const gsb = computed(() => detail.value?.lead_time?.gsb ?? null)
const leadHours = computed(() => (gsb.value && gsb.value.state !== 'not_polled' ? gsb.value.at_least_hours : null))

async function load() {
  error.value = ''
  try {
    detail.value = await apiJson<CaseDetail>(path.value)
  } catch (e) {
    detail.value = null
    error.value = t('failed', { error: String(e) })
  }
}

async function act(what: Key, work: () => Promise<unknown>) {
  error.value = ''
  notice.value = ''
  try {
    await work()
    notice.value = t('done', { what: t(what) })
    await load()
    emit('changed')
  } catch (e) {
    error.value = t('failed', { error: String(e) })
  }
}

const reviewer = () => ({ reviewer: officerName() })

function review(decision: 'confirm' | 'reject') {
  const evidenceId = detail.value?.evidence_id
  if (!evidenceId) return
  const reason = decision === 'reject' ? rejectReason.value : null
  act(decision, () => postJson(`/v1/review/${evidenceId}`, { decision, reason, reviewer: officerName() }))
}

watch(() => props.domain, load, { immediate: true })
</script>

<template>
  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <p v-if="!detail && !error" class="muted">{{ t('loading') }}</p>
  <article v-if="detail" class="panel case-card">
    <CaseTitle :domain="detail.domain" :title="detail.title" :url="detail.url" />

    <p class="score-line">
      <span :class="['badge', detail.verdict]">{{ detail.verdict }}</span>
      {{ t('score') }}: <strong>{{ detail.score }}</strong>
      <span class="badge neutral">{{ detail.state }}</span>
    </p>
    <p v-if="leadHours !== null" class="lead">{{ t('leadTime', { n: leadHours }) }}</p>

    <h3>{{ t('screenshot') }}</h3>
    <BlobImage v-if="detail.has_screenshot && detail.evidence_id" :path="`/v1/admin/evidence/${detail.evidence_id}/screenshot.png`" />
    <p v-else class="muted">{{ t('noScreenshot') }}</p>

    <h3>{{ t('reasons') }}</h3>
    <ul v-if="detail.reasons.length" class="reasons">
      <li v-for="reason in detail.reasons" :key="reason.code">
        <span class="mono">+{{ reason.weight }}</span>
        <span>{{ reason.en }}</span>
        <span dir="rtl" lang="ar">{{ reason.ar }}</span>
      </li>
    </ul>
    <p v-else class="muted">{{ t('noReasons') }}</p>

    <h3>{{ t('location') }}</h3>
    <LocationLines v-if="detail.location" :location="detail.location" />

    <h3>{{ t('infrastructure') }}</h3>
    <dl class="facts">
      <dt>{{ t('registrar') }}</dt>
      <dd>{{ detail.infrastructure.registrar ?? t('unknown') }}</dd>
      <dt>{{ t('registeredAt') }}</dt>
      <dd>{{ detail.infrastructure.registered_at ? formatTime(detail.infrastructure.registered_at) : t('unknown') }}</dd>
      <dt>{{ t('ip') }}</dt>
      <dd class="mono">{{ detail.infrastructure.ip ? defang(detail.infrastructure.ip) : t('unknown') }}</dd>
      <dt>{{ t('network') }}</dt>
      <dd>{{ detail.infrastructure.ip_owner ?? detail.infrastructure.ip_network ?? t('unknown') }}</dd>
      <dt>{{ t('nameServers') }}</dt>
      <dd class="mono">{{ (detail.infrastructure.name_servers ?? []).map(defang).join(', ') || t('unknown') }}</dd>
    </dl>

    <h3>{{ t('sources') }}</h3>
    <p>{{ detail.sources.join(', ') }} · {{ t('reports') }}: {{ detail.reports }} · {{ t('hits') }}: {{ detail.hits }}</p>

    <h3>{{ t('reportNotes') }}</h3>
    <ul v-if="detail.report_notes.length" class="notes">
      <li v-for="note in detail.report_notes" :key="note.id">
        <span class="muted">{{ formatTime(note.created_at) }}</span>
        <q>{{ note.note }}</q>
      </li>
    </ul>
    <p v-else class="muted">{{ t('noNotes') }}</p>

    <h3>{{ t('campaign') }}</h3>
    <RouterLink v-if="detail.campaign_id" :to="`/campaigns/${detail.campaign_id}`">{{ detail.campaign_id }}</RouterLink>
    <p v-else class="muted">{{ t('noCampaign') }}</p>

    <h3>{{ t('pastReviews') }}</h3>
    <ul v-if="detail.reviews.length">
      <li v-for="past in detail.reviews" :key="past.id">
        {{ past.decision }}{{ past.reason ? ` (${past.reason})` : '' }} · {{ past.reviewer }} · {{ formatTime(past.reviewed_at) }}
      </li>
    </ul>
    <p v-else class="muted">{{ t('noReviews') }}</p>

    <p v-if="!detail.evidence_id" class="muted">{{ t('noEvidence') }}</p>
    <div class="actions">
      <button :disabled="!detail.evidence_id" @click="review('confirm')">{{ t('confirm') }}</button>
      <select v-model="rejectReason" :aria-label="t('rejectReason')" :disabled="!detail.evidence_id">
        <option value="">{{ t('chooseReason') }}</option>
        <option v-for="code in REJECT_REASONS" :key="code" :value="code">{{ t(`reason_${code}`) }}</option>
      </select>
      <button class="danger" :disabled="!detail.evidence_id || !rejectReason" @click="review('reject')">{{ t('reject') }}</button>
    </div>
    <div class="actions">
      <button class="secondary" @click="act('recheck', () => postJson(`${path}/recheck`, reviewer()))">{{ t('recheck') }}</button>
      <button class="secondary" @click="act('watch', () => postJson(`${path}/watch`, reviewer()))">{{ t('watch') }}</button>
      <button
        v-if="detail.state === 'auto_confirmed'"
        class="secondary"
        @click="act('undoAuto', () => postJson(`${path}/undo-auto-confirm`, reviewer()))"
      >
        {{ t('undoAuto') }}
      </button>
      <template v-if="detail.evidence_id">
        <button class="secondary" @click="download(`/v1/evidence/${detail.evidence_id}.pdf`, `evidence-${detail.evidence_id}.pdf`)">
          {{ t('downloadPdf') }}
        </button>
        <button class="secondary" @click="download(`/v1/evidence/${detail.evidence_id}.json`, `evidence-${detail.evidence_id}.json`)">
          {{ t('downloadJson') }}
        </button>
      </template>
    </div>
    <p v-if="notice" class="notice" role="status">{{ notice }}</p>
  </article>
</template>
