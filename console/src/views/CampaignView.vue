<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { apiJson, postJson, errorText } from '../api'
import CampaignGraph from '../components/CampaignGraph.vue'
import EntityCard from '../components/EntityCard.vue'
import LocationLines from '../components/LocationLines.vue'
import ReasonConfirm from '../components/ReasonConfirm.vue'
import { band, isHigh } from '../bands'
import { defang } from '../defang'
import { demoRunning } from '../demo'
import { isDemoOnly } from '../demoData'
import { t } from '../i18n'
import { officerName } from '../session'
import type { CampaignDetail, CampaignHeader, ExcludeResult, Graph, MergeResult, Pivot } from '../types'

const props = defineProps<{ id: string }>()
const detail = ref<CampaignDetail | null>(null)
const graph = ref<Graph | null>(null)
const error = ref('')
const ticked = reactive(new Set<string>())
const result = ref<{ confirmed: string[]; skipped: { domain: string; reason: string }[] } | null>(null)
const router = useRouter()
const busy = ref(false)
const actionError = ref('')
const notice = ref('')
const excluding = ref<string | null>(null)
const others = ref<CampaignHeader[]>([])
const mergeWith = ref('')
const entity = ref<{ kind: string; value: string } | null>(null)
const pivot = ref<Pivot | null>(null)

const base = computed(() => `/v1/admin/campaigns/${encodeURIComponent(props.id)}`)

// The sample campaign exists only in the demo: leave it when the demo stops.
watch(demoRunning, (running) => {
  if (!running && isDemoOnly(props.id)) void router.replace('/campaigns')
})
const confirmedShown = computed(() => {
  const refused = new Set(result.value?.skipped.map((skip) => skip.domain))
  return (result.value?.confirmed ?? []).filter((domain) => !refused.has(domain))
})

function refusedText(why: string): string {
  if (why === 'official') return t('refusedOfficial')
  if (why === 'allowlisted') return t('refusedAllowlisted')
  return why
}

async function load() {
  try {
    const [loadedDetail, loadedGraph] = await Promise.all([
      apiJson<CampaignDetail>(base.value),
      apiJson<Graph>(`${base.value}/graph`),
    ])
    detail.value = loadedDetail
    graph.value = loadedGraph
    ticked.clear()
    for (const row of loadedDetail.domains) {
      if (!row.excluded && (row.tick ?? (row.score !== null && isHigh(row.score)))) ticked.add(row.domain)
    }
  } catch (e) {
    error.value = t('failed', { error: errorText(e) })
  }
}

function toggle(domain: string, on: boolean) {
  if (on) ticked.add(domain)
  else ticked.delete(domain)
}

function confirmAll() {
  void act(async () => {
    result.value = await postJson(`${base.value}/confirm`, { domains: [...ticked], reviewer: officerName() })
    await load()
  })
}

async function loadOthers() {
  try {
    others.value = (await apiJson<{ campaigns: CampaignHeader[] }>('/v1/admin/campaigns')).campaigns
  } catch (e) {
    actionError.value = t('failed', { error: errorText(e) })
  }
}

async function act(work: () => Promise<void>) {
  actionError.value = ''
  notice.value = ''
  busy.value = true
  try {
    await work()
  } catch (e) {
    actionError.value = t('failed', { error: errorText(e) })
  } finally {
    busy.value = false
  }
}

function exclude(reason: string) {
  const domain = excluding.value
  if (!domain) return
  void act(async () => {
    await postJson<ExcludeResult>(`${base.value}/exclude`, { domain, reviewer: officerName(), reason })
    excluding.value = null
    notice.value = t('campExcluded', { domain: defang(domain) })
    await load()
  })
}

function merge(reason: string) {
  const other = mergeWith.value
  if (!other) return
  void act(async () => {
    const merged = await postJson<MergeResult>('/v1/admin/campaigns/merge', {
      ids: [props.id, other],
      reviewer: officerName(),
      reason,
    })
    mergeWith.value = ''
    notice.value = t('campMerged', { id: merged.id })
    if (merged.id !== props.id) await router.push(`/campaigns/${encodeURIComponent(merged.id)}`)
    else await load()
  })
}

function runPivot(target?: { kind: string; value: string }) {
  void act(async () => {
    pivot.value = await postJson<Pivot>(`${base.value}/pivot`, target ?? {})
  })
}

watch(
  () => props.id,
  () => {
    detail.value = null
    graph.value = null
    error.value = ''
    result.value = null
    actionError.value = ''
    excluding.value = null
    entity.value = null
    pivot.value = null
    mergeWith.value = ''
    void load()
    void loadOthers()
  },
  { immediate: true },
)
</script>

<template>
  <RouterLink class="link" to="/campaigns">{{ t('back') }}</RouterLink>
  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <p v-else-if="!detail || !graph" class="muted" role="status">{{ t('loading') }}</p>
  <template v-else>
    <div class="page-head">
      <h1>{{ detail.name }}</h1>
      <span class="status-chip" :class="detail.status === 'campaign' ? 'confirmed' : 'suspected'">{{
        detail.status === 'campaign' ? t('campaignConfirmed') : t('campaignSuspected')
      }}</span>
      <span v-if="detail.brand" class="muted">{{ detail.brand }}</span>
    </div>

    <div class="card">
      <div class="card-section">
        <h2 class="section-title">{{ t('campaignDomains') }}</h2>
        <table class="table">
          <thead>
            <tr>
              <th></th>
              <th>{{ t('domain') }}</th>
              <th>{{ t('state') }}</th>
              <th>{{ t('score') }}</th>
              <th>{{ t('reasons') }}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in detail.domains" :key="row.domain">
              <td>
                <input
                  type="checkbox"
                  :checked="ticked.has(row.domain)"
                  :disabled="!!row.excluded"
                  :aria-label="defang(row.domain)"
                  @change="toggle(row.domain, ($event.target as HTMLInputElement).checked)"
                />
              </td>
              <td :data-label="t('domain')" class="mono">{{ defang(row.domain) }}</td>
              <td :data-label="t('state')">{{ row.state }}</td>
              <td :data-label="t('score')">
                <span v-if="row.score !== null" class="q-score" :class="band(row.score)">{{ row.score }}</span>
                <template v-else>—</template>
              </td>
              <td :data-label="t('reasons')">
                <span v-if="row.excluded" class="muted">{{ t('excluded', { why: row.excluded }) }}</span>
              </td>
              <td :data-label="t('campExclude')">
                <span v-if="row.excluded" class="tag">{{ t('campExcludedTag') }}</span>
                <button
                  v-else
                  type="button"
                  class="btn danger"
                  :disabled="busy"
                  @click="excluding = row.domain"
                >
                  {{ t('campExclude') }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
        <div class="actions">
          <button class="btn primary" :disabled="!ticked.size || busy" @click="confirmAll">{{ t('confirmAll') }}</button>
        </div>
        <ReasonConfirm
          v-if="excluding"
          :key="excluding"
          :title="t('campExcludeTitle', { domain: defang(excluding) })"
          :action-label="t('campExclude')"
          :busy="busy"
          @confirm="exclude($event)"
          @cancel="excluding = null"
        />
        <p v-if="notice" class="notice" role="status">{{ notice }}</p>
        <p v-if="actionError" class="error" role="alert">{{ actionError }}</p>
        <div v-if="result">
          <p v-if="confirmedShown.length">{{ t('confirmedList') }}: {{ confirmedShown.map(defang).join(', ') }}</p>
          <template v-if="result.skipped.length">
            <h3 class="section-title">{{ t('campRefusedTitle') }}</h3>
            <ul class="refused">
              <li v-for="skip in result.skipped" :key="skip.domain">
                <span class="mono">{{ defang(skip.domain) }}</span>: {{ refusedText(skip.reason) }}
              </li>
            </ul>
          </template>
        </div>
      </div>

      <div class="card-section">
        <h2 class="section-title">{{ t('campMergeTitle') }}</h2>
        <label class="merge-field">
          <span>{{ t('campMergeWith') }}</span>
          <select v-model="mergeWith" :disabled="busy">
            <option value=""></option>
            <option v-for="other in others.filter((c) => c.id !== props.id)" :key="other.id" :value="other.id">
              {{ other.name }} ({{ other.id }})
            </option>
          </select>
        </label>
        <p class="muted">{{ t('campMergeNote') }}</p>
        <ReasonConfirm
          :title="t('campMergeTitle')"
          :action-label="t('campMerge')"
          :busy="busy || !mergeWith"
          @confirm="merge"
          @cancel="mergeWith = ''"
        />
      </div>

      <div class="card-section">
        <h2 class="section-title">{{ t('campPivotTitle') }}</h2>
        <p class="muted">{{ t('campPivotNote') }}</p>
        <div class="actions">
          <button type="button" class="btn" :disabled="busy" @click="runPivot()">{{ t('campPivot') }}</button>
        </div>
        <template v-if="pivot">
          <p>{{ t('campPivotTotal', { n: pivot.total }) }}</p>
          <p v-if="!pivot.leads.length" class="empty">{{ t('campPivotEmpty') }}</p>
          <table v-else class="table leads">
            <thead>
              <tr>
                <th>{{ t('domain') }}</th>
                <th>{{ t('campPivotVia') }}</th>
                <th>{{ t('colStatus') }}</th>
                <th>{{ t('score') }}</th>
                <th>{{ t('campaign') }}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="lead in pivot.leads" :key="lead.domain">
                <td :data-label="t('domain')" class="mono">{{ defang(lead.domain) }}</td>
                <td :data-label="t('campPivotVia')">
                  <span v-for="(via, index) in lead.via" :key="index" class="tag">
                    {{ via.kind }} {{ defang(via.label) }} · {{ t(via.strong ? 'strong' : 'weak') }}
                  </span>
                </td>
                <td :data-label="t('colStatus')">
                  <span v-if="lead.status" class="status-chip">{{ lead.status }}</span>
                  <template v-else>—</template>
                </td>
                <td :data-label="t('score')">
                  <span v-if="lead.score !== null" class="q-score" :class="band(lead.score)">{{ lead.score }}</span>
                </td>
                <td :data-label="t('campaign')">
                  <RouterLink v-if="lead.campaign" class="link" :to="`/campaigns/${encodeURIComponent(lead.campaign)}`">{{
                    lead.campaign
                  }}</RouterLink>
                </td>
                <td :data-label="t('openInQueue')">
                  <RouterLink class="link" :to="`/queue/${encodeURIComponent(lead.domain)}`">{{ t('openInQueue') }}</RouterLink>
                </td>
              </tr>
            </tbody>
          </table>
        </template>
      </div>

      <div class="card-section">
        <h2 class="section-title">{{ t('shared') }}</h2>
        <table v-if="detail.shared.length" class="table">
          <tbody>
            <tr v-for="item in detail.shared" :key="`${item.kind}:${item.value}`">
              <td :data-label="t('campEntityKind')">{{ item.kind }}</td>
              <td :data-label="t('campEntityValue')" class="mono">{{ defang(item.value) }}</td>
              <td :data-label="t('campStrength')">{{ t(item.strength === 'strong' ? 'strong' : 'weak') }}</td>
              <td :data-label="t('domainCount')">{{ t('domainCount') }}: {{ item.domain_count }}</td>
              <td :data-label="t('details')">
                <button type="button" class="btn ghost" @click="entity = { kind: item.kind, value: item.value }">
                  {{ t('details') }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
        <EntityCard
          v-if="entity"
          :key="`${entity.kind}:${entity.value}`"
          :kind="entity.kind"
          :value="entity.value"
          :busy="busy"
          @close="entity = null"
          @pivot="runPivot"
        />
      </div>

      <div class="card-section">
        <h2 class="section-title">{{ t('locations') }}</h2>
        <div v-for="(place, index) in detail.locations" :key="index" class="place">
          <LocationLines :location="place" />
          <p class="muted">{{ t('domainCount') }}: {{ place.domains }}</p>
        </div>
      </div>

      <div class="card-section">
        <h2 class="section-title">{{ t('graph') }}</h2>
        <CampaignGraph :graph="graph" />
      </div>
    </div>
  </template>
</template>

<style scoped>
.merge-field {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 4px;
  max-inline-size: 28rem;
}
.merge-field select {
  inline-size: 100%;
  min-inline-size: 0;
}
.refused {
  margin-block: 0;
  padding-inline-start: var(--space-3, 16px);
}
.page-head {
  align-items: center;
  gap: 12px;
}
</style>
