<script setup lang="ts">
// The case card (docs/admin-dashboard.md, "Queue"). Everything taken from the page (title, text, URLs,
// report notes) is rendered as text; the screenshot is a PNG served by core.
import { computed, ref, watch } from 'vue'
import { get, post, evidenceUrl, previewUrl } from '../api'
import { t } from '../i18n'
import type { MessageKey } from '../i18n/en'
import { reviewer } from '../session'
import type { CaseDetail } from '../types'
import DefangedDomain from './DefangedDomain.vue'
import ReasonList from './ReasonList.vue'
import StatusBadge from './StatusBadge.vue'

const props = defineProps<{ domain: string; compact?: boolean }>()
const emit = defineEmits<{ changed: [domain: string, decision: string] }>()

const detail = ref<CaseDetail | null>(null)
const error = ref('')
const notice = ref('')
const busy = ref(false)
const rejecting = ref(false)
const note = ref('')
const REASONS = ['legitimate_site', 'not_a_scam', 'insufficient_evidence', 'duplicate'] as const

async function load() {
  error.value = ''
  notice.value = ''
  try {
    detail.value = await get<CaseDetail>(`/v1/admin/cases/${encodeURIComponent(props.domain)}`)
  } catch (e) {
    detail.value = null
    error.value = (e as Error).message
  }
}

watch(() => props.domain, load, { immediate: true })

const latest = computed(() => detail.value?.latest ?? null)
const evidenceId = computed(() => latest.value?.evidence_id ?? null)
const aiSource = computed(() => latest.value?.sources.find((s) => s.id === 'ai'))
const decided = computed(() => ['confirmed', 'cleared', 'official', 'allowlisted'].includes(detail.value?.status ?? '')
  && detail.value?.status_source !== 'police')

async function act(fn: () => Promise<string>) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    notice.value = await fn()
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = false
  }
}

function confirm() {
  if (!evidenceId.value) {
    error.value = 'No evidence record yet: run a deep analysis first.'
    return
  }
  act(async () => {
    const result = await post<{ blocklist_version: number | null }>(`/v1/review/${evidenceId.value}`, {
      decision: 'confirm', reviewer: reviewer(), note: note.value,
    })
    emit('changed', props.domain, 'confirm')
    await load()
    return `Confirmed. Blocklist version ${result.blocklist_version ?? '—'}.`
  })
}

function reject(reason: (typeof REASONS)[number]) {
  rejecting.value = false
  if (!evidenceId.value) {
    error.value = 'No evidence record yet: run a deep analysis first.'
    return
  }
  act(async () => {
    await post(`/v1/review/${evidenceId.value}`, { decision: 'reject', reviewer: reviewer(), reason, note: note.value })
    emit('changed', props.domain, 'reject')
    await load()
    return `Rejected: ${t(`reject.${reason}` as MessageKey)}.`
  })
}

function recheck() {
  act(async () => {
    const result = await post<{ check_id: string; deep_status: string }>(
      `/v1/admin/cases/${encodeURIComponent(props.domain)}/recheck`, { reviewer: reviewer() })
    setTimeout(load, 15_000)
    return `Deep analysis ${result.deep_status} (${result.check_id}).`
  })
}

function watchSite() {
  act(async () => {
    const result = await post<{ next_check_at: string }>(`/v1/admin/cases/${encodeURIComponent(props.domain)}/watch`,
      { reviewer: reviewer() })
    await load()
    return `Watching. Next check ${new Date(result.next_check_at).toLocaleString()}.`
  })
}

function openReject() {
  rejecting.value = true
}

defineExpose({ confirm, openReject, recheck, watchSite, reject, rejecting })

function fmt(value: string | null | undefined): string {
  return value ? new Date(value).toLocaleString() : '—'
}
</script>

<template>
  <div class="card case">
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="notice" class="notice">{{ notice }}</p>
    <p v-if="!detail && !error" class="muted">{{ t('common.loading') }}</p>
    <template v-if="detail">
      <div class="row head">
        <DefangedDomain :display="detail.display" />
        <StatusBadge v-if="latest" :value="latest.verdict" :score="latest.score" />
        <StatusBadge v-if="detail.status" :value="detail.status" />
        <span v-if="detail.status_source === 'police'" class="badge">auto</span>
        <span v-if="latest?.brand" class="badge">{{ latest.brand }}</span>
        <span class="spacer" />
        <RouterLink v-if="compact" :to="{ name: 'case', params: { domain: detail.domain } }">{{ t('case.open') }}</RouterLink>
      </div>
      <p v-if="latest" class="muted small mono">{{ latest.display_url }}<template v-if="latest.display_final_url && latest.display_final_url !== latest.display_url"> → {{ latest.display_final_url }}</template></p>

      <div class="row actions">
        <button class="primary" :disabled="busy || decided" @click="confirm">{{ t('case.confirm') }} <kbd>C</kbd></button>
        <button :disabled="busy || decided" @click="openReject">{{ t('case.reject') }} <kbd>R</kbd></button>
        <button :disabled="busy" @click="recheck">{{ t('case.recheck') }} <kbd>D</kbd></button>
        <button :disabled="busy" @click="watchSite">{{ t('case.watch') }} <kbd>W</kbd></button>
        <a v-if="evidenceId" class="button" :href="evidenceUrl(evidenceId, 'pdf')" target="_blank" rel="noopener">PDF</a>
      </div>
      <input v-model="note" class="note" :placeholder="t('case.note')" maxlength="2000" />

      <div v-if="rejecting" class="modal-back" @click.self="rejecting = false">
        <div class="modal">
          <h2>{{ t('reject.title') }}</h2>
          <div class="grid">
            <button v-for="(code, i) in REASONS" :key="code" @click="reject(code)">
              <kbd>{{ i + 1 }}</kbd> {{ t(`reject.${code}` as MessageKey) }}
            </button>
            <button class="ghost" @click="rejecting = false">{{ t('common.cancel') }}</button>
          </div>
        </div>
      </div>

      <div class="grid" :class="compact ? '' : 'cols-2'">
        <section>
          <img v-if="evidenceId && latest?.preview" class="shot" :src="previewUrl(evidenceId)" alt="Phone screenshot of the page" />
          <h3>{{ t('case.reasons') }}</h3>
          <ReasonList v-if="latest" :reasons="latest.reasons" />
          <p v-if="latest?.deep_status && latest.deep_status !== 'done'" class="muted small">deep: {{ latest.deep_status }}</p>
          <h3>{{ t('case.sources') }}</h3>
          <div class="row">
            <span v-for="s in latest?.sources ?? []" :key="s.id" class="badge" :class="s.status === 'hit' ? 'block' : ''" :title="s.detail ?? ''">
              {{ s.id }}: {{ s.status }}
            </span>
          </div>
          <p v-if="aiSource?.detail" class="small"><span class="badge ai">{{ t('case.ai') }}</span> {{ aiSource.detail }}</p>
        </section>
        <section>
          <template v-if="detail.page">
            <h3>{{ t('case.page') }}</h3>
            <dl class="kv small">
              <dt>title</dt><dd>{{ detail.page.title ?? '—' }}</dd>
              <dt>asks for</dt><dd>{{ detail.page.asks_for?.join(', ') || '—' }}</dd>
              <dt>phones</dt><dd class="mono">{{ detail.page.phones?.join(', ') || '—' }}</dd>
              <dt>posts to</dt><dd class="mono">{{ detail.page.payment_hosts?.join(', ') || '—' }}</dd>
              <dt>HTTP</dt><dd>{{ detail.page.status ?? '—' }} · {{ detail.page.lang ?? '' }}</dd>
              <dt v-if="detail.visual">looks like</dt><dd v-if="detail.visual">{{ detail.visual.brand_id }} ({{ Math.round(detail.visual.similarity * 100) }}%)</dd>
            </dl>
            <details v-if="detail.page.text_excerpt" class="small">
              <summary>page text</summary>
              <pre class="excerpt">{{ detail.page.text_excerpt }}</pre>
            </details>
          </template>
          <template v-if="detail.infra">
            <h3>{{ t('case.infra') }}</h3>
            <dl class="kv small">
              <dt>IP</dt><dd class="mono">{{ detail.infra.a?.join(', ') || '—' }}</dd>
              <dt>ASN</dt><dd>{{ Object.values(detail.infra.asn ?? {}).map((a) => `AS${a.asn} ${a.name ?? ''}`).join(', ') || '—' }}</dd>
              <dt>NS</dt><dd class="mono">{{ detail.infra.ns?.join(', ') || '—' }}</dd>
              <dt>registrar</dt><dd>{{ detail.infra.rdap?.registrar ?? '—' }}</dd>
              <dt>registered</dt><dd>{{ fmt(detail.infra.rdap?.created) }}</dd>
            </dl>
          </template>
          <h3>{{ t('case.discovery') }}</h3>
          <ul class="small plain">
            <li v-for="d in detail.discovery" :key="d.source">{{ d.source }} · {{ fmt(d.first_seen) }}</li>
            <li v-if="!detail.discovery.length" class="muted">—</li>
          </ul>
          <h3>{{ t('case.reports') }} ({{ detail.reports.count }})</h3>
          <ul class="small plain">
            <li v-for="r in detail.reports.notes" :key="r.at">“{{ r.note }}” <span class="muted">{{ fmt(r.at) }}</span></li>
          </ul>
          <p v-if="Object.keys(detail.hits).length" class="small">hits: {{ Object.entries(detail.hits).map(([c, n]) => `${c} ${n}`).join(' · ') }}</p>
          <template v-if="detail.campaign">
            <h3>{{ t('case.campaign') }}</h3>
            <RouterLink :to="{ name: 'campaign', params: { id: detail.campaign.id } }">{{ detail.campaign.name ?? detail.campaign.id }}</RouterLink>
            <span class="muted small"> · {{ detail.campaign.domain_count }} sites</span>
          </template>
          <p v-if="detail.watchlist" class="small">watchlist: {{ detail.watchlist.reason }} · next {{ fmt(detail.watchlist.next_check_at) }}</p>
          <template v-if="detail.reviews.length">
            <h3>{{ t('case.reviews') }}</h3>
            <ul class="small plain">
              <li v-for="r in detail.reviews" :key="r.at">{{ r.decision }}<template v-if="r.reason"> ({{ r.reason }})</template> · {{ r.reviewer }} · {{ fmt(r.at) }}<template v-if="r.note"> · {{ r.note }}</template></li>
            </ul>
          </template>
          <template v-if="!compact">
            <h3>{{ t('case.history') }}</h3>
            <table class="small">
              <tr v-for="h in detail.history" :key="h.check_id"><td>{{ fmt(h.at) }}</td><td>{{ h.source }}</td><td><StatusBadge :value="h.verdict" :score="h.score" /></td><td>{{ h.stage }}</td></tr>
            </table>
          </template>
        </section>
      </div>
    </template>
  </div>
</template>

<style scoped>
.head { margin-bottom: 0.25rem; font-size: 1.05rem; }
.actions { margin: 0.5rem 0; }
.note { width: 100%; margin-bottom: 0.75rem; }
.shot { width: 100%; max-width: 260px; border: 1px solid var(--line); border-radius: 6px; display: block; margin-bottom: 0.75rem; }
.excerpt { white-space: pre-wrap; max-height: 14rem; overflow: auto; background: var(--surface-2); padding: 0.5rem; border-radius: 6px; }
ul.plain { list-style: none; padding: 0; margin: 0 0 0.5rem; }
section h3 { margin-top: 0.75rem; }
</style>
