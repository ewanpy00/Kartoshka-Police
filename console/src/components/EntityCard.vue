<script setup lang="ts">
import { ref, watch } from 'vue'
import { apiJson, errorText } from '../api'
import { band } from '../bands'
import { defang } from '../defang'
import { formatTime, t } from '../i18n'
import type { EntityCard } from '../types'

const props = defineProps<{ kind: string; value: string; busy: boolean }>()
const emit = defineEmits<{ close: []; pivot: [entity: { kind: string; value: string }] }>()

const card = ref<EntityCard | null>(null)
const error = ref('')

async function load() {
  const { kind, value } = props
  card.value = null
  error.value = ''
  try {
    const loaded = await apiJson<EntityCard>(`/v1/admin/entities/${encodeURIComponent(kind)}/${encodeURIComponent(value)}`)
    if (kind === props.kind && value === props.value) card.value = loaded
  } catch (e) {
    if (kind === props.kind && value === props.value) error.value = t('failed', { error: errorText(e) })
  }
}

watch(() => [props.kind, props.value], load, { immediate: true })
</script>

<template>
  <section class="entity-card">
    <div class="entity-head">
      <h3 class="section-title">{{ t('campEntityTitle') }}</h3>
      <button type="button" class="btn ghost" @click="emit('close')">{{ t('close') }}</button>
    </div>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-else-if="!card" class="muted" role="status">{{ t('loading') }}</p>
    <template v-else>
      <dl class="kv">
        <dt>{{ t('campEntityKind') }}</dt>
        <dd>{{ card.kind }}</dd>
        <dt>{{ t('campEntityValue') }}</dt>
        <dd class="mono">{{ defang(card.value) }}</dd>
        <template v-if="card.label !== card.value">
          <dt>{{ t('campEntityLabel') }}</dt>
          <dd class="mono">{{ defang(card.label) }}</dd>
        </template>
        <template v-if="card.first_seen">
          <dt>{{ t('campEntityFirstSeen') }}</dt>
          <dd>{{ formatTime(card.first_seen) }}</dd>
        </template>
        <dt>{{ t('campEntityDomains') }}</dt>
        <dd>{{ card.domain_count }}</dd>
      </dl>
      <p v-if="card.hub" class="notice">{{ t('campEntityHub') }}</p>
      <table v-if="card.domains.length" class="table">
        <thead>
          <tr>
            <th>{{ t('domain') }}</th>
            <th>{{ t('colStatus') }}</th>
            <th>{{ t('campStrength') }}</th>
            <th>{{ t('campaign') }}</th>
            <th>{{ t('score') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="site in card.domains" :key="site.domain">
            <td :data-label="t('domain')" class="mono">
              {{ defang(site.domain) }}
              <span v-if="site.excluded" class="tag">{{ t('campExcludedTag') }}</span>
            </td>
            <td :data-label="t('colStatus')">{{ site.status ?? '—' }}</td>
            <td :data-label="t('campStrength')">{{ t(site.strength === 'strong' ? 'strong' : 'weak') }}</td>
            <td :data-label="t('campaign')">
              <RouterLink v-if="site.campaign" class="link" :to="`/campaigns/${encodeURIComponent(site.campaign)}`">{{
                site.campaign
              }}</RouterLink>
              <template v-else>—</template>
            </td>
            <td :data-label="t('score')">
              <span v-if="site.score !== null" class="q-score" :class="band(site.score)">{{ site.score }}</span>
              <template v-else>—</template>
            </td>
          </tr>
        </tbody>
      </table>
      <div class="actions">
        <button type="button" class="btn" :disabled="busy" @click="emit('pivot', { kind: card.kind, value: card.value })">
          {{ t('campPivot') }}
        </button>
      </div>
    </template>
  </section>
</template>

<style scoped>
.entity-card {
  margin-block-start: var(--space-3, 16px);
}
.entity-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-2, 8px);
}
</style>
