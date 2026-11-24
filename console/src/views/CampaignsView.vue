<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { apiJson, errorText } from '../api'
import { demoRunning } from '../demo'
import { formatTime, t } from '../i18n'
import type { CampaignHeader } from '../types'

const campaigns = ref<CampaignHeader[]>([])
const error = ref('')
const loaded = ref(false)

async function load() {
  try {
    campaigns.value = (await apiJson<{ campaigns: CampaignHeader[] }>('/v1/admin/campaigns')).campaigns
  } catch (e) {
    error.value = t('failed', { error: errorText(e) })
  }
  loaded.value = true
}

onMounted(load)
// A sample campaign shown during the demo goes as soon as it stops.
watch(demoRunning, (running) => {
  if (running) return
  campaigns.value = []
  loaded.value = false
  void load()
})
</script>

<template>
  <div class="page-head"><h1>{{ t('navCampaigns') }}</h1></div>
  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <p v-else-if="!loaded" class="muted">{{ t('loading') }}</p>
  <div v-else-if="!campaigns.length" class="card empty">{{ t('campaignsEmpty') }}</div>
  <div v-else class="card">
    <table class="table">
      <thead>
        <tr>
          <th>{{ t('campaign') }}</th>
          <th>{{ t('brand') }}</th>
          <th>{{ t('state') }}</th>
          <th>{{ t('campaignDomains') }}</th>
          <th>{{ t('firstSeen') }}</th>
          <th>{{ t('lastActivity') }}</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="campaign in campaigns" :key="campaign.id">
          <td :data-label="t('campaign')"><RouterLink class="link" :to="`/campaigns/${campaign.id}`">{{ campaign.name }}</RouterLink></td>
          <td :data-label="t('brand')">{{ campaign.brand ?? '' }}</td>
          <td :data-label="t('state')">
            <span class="status-chip" :class="campaign.status === 'campaign' ? 'confirmed' : 'suspected'">{{
              campaign.status === 'campaign' ? t('campaignConfirmed') : t('campaignSuspected')
            }}</span>
          </td>
          <td :data-label="t('campaignDomains')">{{ t('confirmedOf', { confirmed: campaign.domains.confirmed, total: campaign.domains.total }) }}</td>
          <td :data-label="t('firstSeen')">{{ formatTime(campaign.first_seen) }}</td>
          <td :data-label="t('lastActivity')">{{ formatTime(campaign.last_activity_at) }}</td>
          <td>{{ campaign.active ? t('active') : t('inactive') }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
