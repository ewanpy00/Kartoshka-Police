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
  <section class="panel">
    <h1>{{ t('helplines') }}</h1>
    <div class="actions">
      <button class="secondary" @click="save">{{ t('downloadCsv') }}</button>
      <span class="muted">{{ t('csvNote') }}</span>
    </div>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-else-if="!loaded" class="muted">{{ t('loading') }}</p>
    <p v-else-if="!numbers.length" class="muted">{{ t('helplinesEmpty') }}</p>
    <table v-else>
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
          <td class="mono">{{ row.phone }}</td>
          <td>{{ row.brand ?? '' }}</td>
          <td>{{ row.source }}</td>
          <td class="mono">{{ defang(row.domain) }}</td>
          <td>{{ formatTime(row.first_seen) }}</td>
          <td>{{ row.confirmed ? t('numberConfirmed') : t('numberAwaiting') }}</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>
