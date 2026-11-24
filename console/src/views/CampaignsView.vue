<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { apiJson, errorText } from '../api'
import { formatTime, t } from '../i18n'
import type { CampaignHeader } from '../types'

const campaigns = ref<CampaignHeader[]>([])
const error = ref('')
const loaded = ref(false)

onMounted(async () => {
  try {
    campaigns.value = (await apiJson<{ campaigns: CampaignHeader[] }>('/v1/admin/campaigns')).campaigns
  } catch (e) {
    error.value = t('failed', { error: errorText(e) })
  }
  loaded.value = true
})
</script>

<template>
  <section class="panel">
    <h1>{{ t('campaigns') }}</h1>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-else-if="!loaded" class="muted">{{ t('loading') }}</p>
    <p v-else-if="!campaigns.length" class="muted">{{ t('campaignsEmpty') }}</p>
    <table v-else>
      <thead>
        <tr>
          <th>{{ t('campaign') }}</th>
          <th>{{ t('brand') }}</th>
          <th>{{ t('campaignDomains') }}</th>
          <th>{{ t('lastActivity') }}</th>
          <th>{{ t('state') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="campaign in campaigns" :key="campaign.id">
          <td><RouterLink :to="`/campaigns/${campaign.id}`">{{ campaign.name }}</RouterLink></td>
          <td>{{ campaign.brand ?? '' }}</td>
          <td>{{ t('confirmedOf', { confirmed: campaign.domains.confirmed, total: campaign.domains.total }) }}</td>
          <td>{{ formatTime(campaign.last_activity_at) }}</td>
          <td>{{ campaign.active ? t('active') : t('inactive') }}</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>
