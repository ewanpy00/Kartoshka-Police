<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { apiJson, download, errorText } from '../api'
import { defang } from '../defang'
import { formatTime, t } from '../i18n'
import type { Helpline } from '../types'

const numbers = ref<Helpline[]>([])
const error = ref('')
const loaded = ref(false)

async function save() {
  try {
    await download('/v1/admin/helplines.csv', 'helplines.csv')
  } catch (e) {
    error.value = t('failed', { error: errorText(e) })
  }
}

onMounted(async () => {
  try {
    numbers.value = (await apiJson<{ numbers: Helpline[] }>('/v1/admin/helplines')).numbers
  } catch (e) {
    error.value = t('failed', { error: errorText(e) })
  }
  loaded.value = true
})
</script>

<template>
  <div class="page-head">
    <h1>{{ t('navHelplines') }}</h1>
    <div class="actions">
      <button class="btn" @click="save">{{ t('downloadCsv') }}</button>
    </div>
  </div>
  <p class="muted note">{{ t('csvNote') }}</p>
  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <div class="card">
    <p v-if="!loaded && !error" class="empty">{{ t('loading') }}</p>
    <p v-else-if="loaded && !numbers.length && !error" class="empty">{{ t('helplinesEmpty') }}</p>
    <table v-else-if="numbers.length" class="table">
      <thead>
        <tr>
          <th>{{ t('phone') }}</th>
          <th>{{ t('brand') }}</th>
          <th>{{ t('source') }}</th>
          <th>{{ t('seenOn') }}</th>
          <th>{{ t('firstSeen') }}</th>
          <th>{{ t('state') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in numbers" :key="`${row.phone}:${row.domain}`">
          <td :data-label="t('phone')" class="mono" dir="ltr">{{ row.phone }}</td>
          <td :data-label="t('brand')">{{ row.brand ?? '' }}</td>
          <td :data-label="t('source')">{{ row.source }}</td>
          <td :data-label="t('seenOn')" class="mono">{{ defang(row.domain) }}</td>
          <td :data-label="t('firstSeen')">{{ formatTime(row.first_seen) }}</td>
          <td :data-label="t('state')">
            <span class="status-chip" :class="row.confirmed ? 'confirmed' : 'suspected'">{{
              row.confirmed ? t('numberConfirmed') : t('numberAwaiting')
            }}</span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.note {
  margin-block: 0 12px;
}
.error {
  margin-block: 0 12px;
}
</style>
