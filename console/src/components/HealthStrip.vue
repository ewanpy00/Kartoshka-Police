<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { startHealth, stopHealth, useHealth } from '../health'
import { healthLevel, healthParts, type HealthLevel } from '../healthLevel'
import { t, type Key } from '../i18n'

const { health, reachable } = useHealth()

const LEVEL_KEY: Record<HealthLevel, Key> = { ok: 'healthOk', degraded: 'healthDegraded', down: 'healthDown' }

const overall = computed(() => healthLevel(health.value))
const overallText = computed(() => t(reachable.value === false ? 'healthUnreachable' : LEVEL_KEY[overall.value]))
const label = computed(() => t('healthStripLabel', { state: overallText.value }))
const items = computed(() => {
  if (!health.value) return []
  const parts = healthParts(health.value)
  return [
    { id: 'redis', label: t('healthRedis'), level: parts.redis },
    { id: 'deep', label: t('healthDeepQueue'), level: parts.deep },
    { id: 'hunter', label: t('healthHunter'), level: parts.hunter },
    { id: 'ai', label: t('healthAiKey'), level: parts.ai },
  ].map((i) => ({ ...i, text: t(LEVEL_KEY[i.level]) }))
})

onMounted(startHealth)
onBeforeUnmount(stopHealth)
</script>

<template>
  <RouterLink v-if="reachable !== null" to="/health" class="health-strip" :aria-label="label" :title="label">
    <span class="mark" :class="overall" aria-hidden="true"></span>
    <span v-for="i in items" :key="i.id" class="item" :title="`${i.label}: ${i.text}`">
      <span class="mark" :class="i.level" aria-hidden="true"></span>
      <span>{{ i.label }}</span>
    </span>
  </RouterLink>
</template>

<style scoped>
.health-strip {
  display: inline-flex;
  align-items: center;
  gap: var(--space-3);
  font-size: var(--fs-12);
  white-space: nowrap;
  color: inherit;
  text-decoration: none;
}
.item {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
}
.mark {
  display: inline-block;
  inline-size: 0.6rem;
  block-size: 0.6rem;
  box-sizing: border-box;
  flex: none;
}
.mark.ok {
  background: var(--c-ok);
  border-radius: 50%;
}
.mark.degraded {
  border: 2px solid var(--c-amber);
  border-radius: 50%;
}
.mark.down {
  background: var(--c-risk);
}
@media (max-width: 700px) {
  .item {
    display: none;
  }
}
</style>
