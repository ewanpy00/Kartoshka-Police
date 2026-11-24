<script setup lang="ts">
import { t } from '../i18n'
import { useStats } from '../stats'

const { awaiting, autoConfirmedToday, chain, medianLead } = useStats()
</script>

<template>
  <div
    v-if="awaiting !== null || autoConfirmedToday !== null || chain !== null || medianLead !== null"
    class="stat-strip"
  >
    <div v-if="awaiting !== null" class="stat">
      <span class="num">{{ awaiting }}</span> {{ t('statAwaiting') }}
    </div>
    <div v-if="autoConfirmedToday !== null" class="stat">
      <span class="num">{{ autoConfirmedToday }}</span> {{ t('statAutoToday') }}
    </div>
    <div v-if="chain !== null" class="stat" :class="chain.intact ? 'ok' : 'bad'">
      <svg v-if="chain.intact" width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 8.5l3.2 3L13 4.5" /></svg>
      {{ chain.intact ? t('statChainIntact', { count: chain.count }) : t('statChainBroken', { seq: chain.brokenSeq ?? '' }) }}
    </div>
    <div v-if="medianLead !== null" class="stat">
      <span class="num">{{ t('statLeadValue', { hours: medianLead.hours }) }}</span> {{ t('statLeadLabel', { cases: medianLead.cases }) }}
    </div>
  </div>
</template>
