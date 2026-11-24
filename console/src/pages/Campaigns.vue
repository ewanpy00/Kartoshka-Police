<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { get } from '../api'
import StatusBadge from '../components/StatusBadge.vue'
import { t } from '../i18n'
import type { CampaignSummary } from '../types'

const rows = ref<CampaignSummary[]>([])
const total = ref(0)
const status = ref('')
const active = ref('')
const brand = ref('')
const error = ref('')

async function load() {
  error.value = ''
  try {
    const page = await get<{ total: number; campaigns: CampaignSummary[] }>('/v1/admin/campaigns', {
      status: status.value, brand: brand.value, active: active.value || undefined,
    })
    rows.value = page.campaigns
    total.value = page.total
  } catch (e) {
    error.value = (e as Error).message
  }
}

onMounted(load)
watch([status, active, brand], load)
</script>

<template>
  <main class="page">
    <div class="row">
      <h1>{{ t('campaigns.title') }} <span class="muted small">({{ total }})</span></h1>
      <span class="spacer" />
      <select v-model="status"><option value="">{{ t('filter.all') }}</option>
        <option value="suspected">{{ t('campaigns.suspected') }}</option><option value="confirmed">{{ t('campaigns.confirmed') }}</option></select>
      <select v-model="active"><option value="">any time</option><option value="true">active (7 days)</option><option value="false">quiet</option></select>
      <input v-model.lazy="brand" size="10" :placeholder="t('filter.brand')" />
    </div>
    <p v-if="error" class="error">{{ error }}</p>
    <div class="card">
      <p v-if="!rows.length" class="muted">No campaigns yet. Two sites that share a phone number, payment endpoint, kit or dedicated IP form one.</p>
      <table v-else>
        <tr><th>campaign</th><th>status</th><th>sites</th><th>confirmed</th><th>last activity</th></tr>
        <tr v-for="c in rows" :key="c.id" class="clickable" @click="$router.push({ name: 'campaign', params: { id: c.id } })">
          <td><strong>{{ c.name ?? c.id }}</strong><div class="muted small mono">{{ c.id }}</div></td>
          <td><StatusBadge :value="c.status" /> <span v-if="c.active" class="badge">active</span></td>
          <td>{{ c.domain_count }}</td>
          <td>{{ c.confirmed_count }}</td>
          <td class="small">{{ c.last_activity_at ? new Date(c.last_activity_at).toLocaleString() : '—' }}</td>
        </tr>
      </table>
    </div>
  </main>
</template>
