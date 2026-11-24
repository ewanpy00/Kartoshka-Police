<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { apiJson } from '../api'
import CaseCard from '../components/CaseCard.vue'
import { defang } from '../defang'
import { t } from '../i18n'
import type { CaseSummary } from '../types'

const route = useRoute()
const router = useRouter()
const filters = reactive({ state: 'open', source: '', brand: '', band: '' })
const cases = ref<CaseSummary[]>([])
const error = ref('')
const loaded = ref(false)

const selected = computed(() => (route.params.domain as string | undefined) ?? null)

async function load() {
  const query = new URLSearchParams({ state: filters.state })
  for (const key of ['source', 'brand', 'band'] as const) {
    if (filters[key]) query.set(key, filters[key])
  }
  try {
    cases.value = (await apiJson<{ cases: CaseSummary[] }>(`/v1/admin/queue?${query}`)).cases
    error.value = ''
  } catch (e) {
    error.value = t('failed', { error: String(e) })
  }
  loaded.value = true
}

watch(filters, load, { immediate: true })
</script>

<template>
  <div class="split">
    <section class="panel">
      <form class="filters" @submit.prevent>
        <label>
          {{ t('state') }}
          <select v-model="filters.state">
            <option value="open">{{ t('stateOpen') }}</option>
            <option value="auto_confirmed">{{ t('stateAutoConfirmed') }}</option>
            <option value="all">{{ t('stateAll') }}</option>
          </select>
        </label>
        <label>
          {{ t('band') }}
          <select v-model="filters.band">
            <option value="">{{ t('any') }}</option>
            <option value="block">{{ t('bandBlock') }}</option>
            <option value="warn">{{ t('bandWarn') }}</option>
            <option value="allow">{{ t('bandAllow') }}</option>
          </select>
        </label>
        <label>
          {{ t('source') }}
          <input v-model.trim="filters.source" />
        </label>
        <label>
          {{ t('brand') }}
          <input v-model.trim="filters.brand" />
        </label>
      </form>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <p v-else-if="!loaded" class="muted">{{ t('loading') }}</p>
      <p v-else-if="!cases.length" class="muted">{{ t('queueEmpty') }}</p>
      <ul v-else class="case-list">
        <li v-for="item in cases" :key="item.domain">
          <button :class="['case-row', { active: item.domain === selected }]" @click="router.push(`/queue/${encodeURIComponent(item.domain)}`)">
            <span class="mono">{{ defang(item.domain) }}</span>
            <span class="muted">{{ item.brand ?? '' }}</span>
            <span :class="['badge', item.verdict]">{{ item.score }}</span>
          </button>
        </li>
      </ul>
    </section>
    <section>
      <CaseCard v-if="selected" :domain="selected" @changed="load" />
      <p v-else class="muted">{{ t('selectCase') }}</p>
    </section>
  </div>
</template>
