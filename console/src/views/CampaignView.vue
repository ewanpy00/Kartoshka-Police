<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { apiJson, postJson, errorText } from '../api'
import CampaignGraph from '../components/CampaignGraph.vue'
import LocationLines from '../components/LocationLines.vue'
import { defang } from '../defang'
import { t } from '../i18n'
import { officerName } from '../session'
import type { CampaignDetail, Graph } from '../types'

const props = defineProps<{ id: string }>()
const detail = ref<CampaignDetail | null>(null)
const graph = ref<Graph | null>(null)
const error = ref('')
const ticked = reactive(new Set<string>())
const result = ref<{ confirmed: string[]; skipped: { domain: string; reason: string }[] } | null>(null)

async function load() {
  try {
    const base = `/v1/admin/campaigns/${encodeURIComponent(props.id)}`
    const [loadedDetail, loadedGraph] = await Promise.all([apiJson<CampaignDetail>(base), apiJson<Graph>(`${base}/graph`)])
    detail.value = loadedDetail
    graph.value = loadedGraph
    ticked.clear()
    for (const row of loadedDetail.domains) {
      if (!row.excluded && (row.tick ?? (row.score !== null && row.score >= 70))) ticked.add(row.domain)
    }
  } catch (e) {
    error.value = t('failed', { error: errorText(e) })
  }
}

function toggle(domain: string, on: boolean) {
  if (on) ticked.add(domain)
  else ticked.delete(domain)
}

async function confirmAll() {
  try {
    result.value = await postJson(`/v1/admin/campaigns/${encodeURIComponent(props.id)}/confirm`, {
      domains: [...ticked],
      reviewer: officerName(),
    })
    error.value = ''
    await load()
  } catch (e) {
    error.value = t('failed', { error: errorText(e) })
  }
}

onMounted(load)
</script>

<template>
  <RouterLink class="link" to="/campaigns">{{ t('back') }}</RouterLink>
  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <p v-else-if="!detail || !graph" class="muted">{{ t('loading') }}</p>
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
                <span v-if="row.score !== null" class="q-score" :class="row.score >= 70 ? 'high' : row.score >= 30 ? 'mid' : 'low'">{{ row.score }}</span>
                <template v-else>—</template>
              </td>
              <td :data-label="t('reasons')">
                <span v-if="row.excluded" class="muted">{{ t('excluded', { why: row.excluded }) }}</span>
              </td>
            </tr>
          </tbody>
        </table>
        <div class="actions">
          <button class="btn primary" :disabled="!ticked.size" @click="confirmAll">{{ t('confirmAll') }}</button>
        </div>
        <div v-if="result">
          <p>{{ t('confirmedList') }}: {{ result.confirmed.map(defang).join(', ') }}</p>
          <p>
            {{ t('skippedList') }}:
            {{ result.skipped.map((skip) => `${defang(skip.domain)} (${skip.reason})`).join(', ') }}
          </p>
        </div>
      </div>

      <div class="card-section">
        <h2 class="section-title">{{ t('shared') }}</h2>
        <table v-if="detail.shared.length" class="table">
          <tbody>
            <tr v-for="item in detail.shared" :key="`${item.kind}:${item.value}`">
              <td>{{ item.kind }}</td>
              <td class="mono">{{ defang(item.value) }}</td>
              <td>{{ t(item.strength === 'strong' ? 'strong' : 'weak') }}</td>
              <td>{{ t('domainCount') }}: {{ item.domain_count }}</td>
            </tr>
          </tbody>
        </table>
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
.page-head {
  align-items: center;
  gap: 12px;
}
</style>
