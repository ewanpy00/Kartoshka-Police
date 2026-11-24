<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { refreshHealth, startHealth, useHealth } from '../health'
import { healthLevel, type HealthLevel } from '../healthLevel'
import { formatTime, t, type Key } from '../i18n'
import type { Budget } from '../types'

const { health, reachable } = useHealth()

const LEVEL_KEY: Record<HealthLevel, Key> = { ok: 'healthOk', degraded: 'healthDegraded', down: 'healthDown' }
const KNOWN_MODELS = new Set(['url_model', 'visual_refs'])

const level = computed(() => healthLevel(health.value))

function modelName(name: string): string {
  return KNOWN_MODELS.has(name) ? t(`healthModel_${name}` as Key) : name
}

function budgetText(budget: Budget): string {
  return budget.limit === null
    ? t('healthBudgetUnlimited', { used: budget.used })
    : t('healthBudgetUsed', { used: budget.used, limit: budget.limit })
}

onMounted(startHealth)
</script>

<template>
  <div class="page-head">
    <h1>{{ t('healthTitle') }}</h1>
    <div class="actions">
      <span v-if="health" class="muted">{{ t('healthChecked', { time: formatTime(health.checked_at) }) }}</span>
      <button type="button" class="btn" @click="refreshHealth()">{{ t('refresh') }}</button>
    </div>
  </div>
  <p v-if="reachable === null" class="muted" role="status">{{ t('loading') }}</p>
  <p v-else-if="!health" class="error" role="alert">{{ t('healthUnreachable') }}</p>
  <template v-else>
    <p class="status-line">
      <span class="mark" :class="level" aria-hidden="true"></span>
      <strong>{{ t(LEVEL_KEY[level]) }}</strong>
    </p>

    <div class="card">
      <div class="card-section">
        <h2 class="section-title">{{ t('healthPipeline') }}</h2>
        <dl class="kv">
          <dt>{{ t('healthRedis') }}</dt>
          <dd>{{ health.redis_ok ? t('healthOk') : t('healthDown') }}</dd>
          <dt>{{ t('healthDeepQueue') }}</dt>
          <dd v-if="health.deep_queue">
            {{ t('healthWaiting', { n: health.deep_queue.waiting }) }},
            {{ t('healthFailed', { n: health.deep_queue.failed }) }},
            {{ t('healthWorkers', { n: health.deep_queue.workers }) }}
          </dd>
          <dd v-else>{{ t('notStated') }}</dd>
          <dt>{{ t('healthDeepRunning') }}</dt>
          <dd>
            {{ health.checks.deep_running }}
            <span v-if="health.checks.deep_stale > 0" class="badge warn">{{
              t('healthDeepStale', { n: health.checks.deep_stale })
            }}</span>
          </dd>
          <dt>{{ t('healthChecksLast') }}</dt>
          <dd>{{ health.checks.last ? formatTime(health.checks.last) : t('notStated') }}</dd>
          <dt>{{ t('healthChecksHour') }}</dt>
          <dd>{{ health.checks.last_hour }}</dd>
          <dt>{{ t('healthEvidence') }}</dt>
          <dd>{{ health.evidence_records }}</dd>
          <dt>{{ t('healthBlocklist') }}</dt>
          <dd class="mono">{{ health.blocklist_version ?? t('notStated') }}</dd>
        </dl>
      </div>
    </div>

    <div class="card">
      <div class="card-section">
        <h2 class="section-title">{{ t('healthHunter') }}</h2>
        <p v-if="health.hunter.length === 0" class="empty">{{ t('healthHunterEmpty') }}</p>
        <table v-else class="table">
          <thead>
            <tr>
              <th>{{ t('source') }}</th>
              <th>{{ t('healthHunterLast') }}</th>
              <th>{{ t('healthHunter24h') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in health.hunter" :key="s.source">
              <td :data-label="t('source')">{{ s.source }}</td>
              <td :data-label="t('healthHunterLast')">{{ s.last ? formatTime(s.last) : t('notStated') }}</td>
              <td :data-label="t('healthHunter24h')">{{ s.last_24h }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="card">
      <div class="card-section">
        <h2 class="section-title">{{ t('healthModels') }}</h2>
        <table class="table">
          <thead>
            <tr>
              <th>{{ t('healthModels') }}</th>
              <th>{{ t('modelUpdated') }}</th>
              <th>{{ t('score') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="m in health.models" :key="m.name">
              <td :data-label="t('healthModels')">{{ modelName(m.name) }}</td>
              <td :data-label="t('modelUpdated')">
                {{ m.updated_at ? formatTime(m.updated_at) : t('healthModelMissing') }}
              </td>
              <td :data-label="t('score')">{{ m.score ?? '' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="card">
      <div class="card-section">
        <h2 class="section-title">{{ t('healthBudgets') }}</h2>
        <dl class="kv">
          <dt>{{ t('healthBudgetAi') }}</dt>
          <dd>
            {{ budgetText(health.budget.ai) }}
            <span v-if="health.budget.ai.reached" class="badge warn">{{ t('healthBudgetAiReached') }}</span>
          </dd>
          <dt>{{ t('healthBudgetDeep') }}</dt>
          <dd>
            {{ budgetText(health.budget.deep) }}
            <span v-if="health.budget.deep.reached" class="badge warn">{{ t('healthBudgetDeepReached') }}</span>
          </dd>
        </dl>
      </div>
    </div>

    <div class="card">
      <div class="card-section">
        <h2 class="section-title">{{ t('healthKeys') }}</h2>
        <dl class="kv">
          <dt>{{ t('healthAiKey') }}</dt>
          <dd>{{ health.ai_key_set ? t('keySet') : t('keyNotSet') }}</dd>
          <dt>{{ t('healthGsbKey') }}</dt>
          <dd>{{ t('notStated') }}</dd>
          <dt>{{ t('healthVtKey') }}</dt>
          <dd>{{ t('notStated') }}</dd>
        </dl>
      </div>
    </div>
  </template>
</template>

<style scoped>
.status-line {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.mark {
  display: inline-block;
  inline-size: 0.75rem;
  block-size: 0.75rem;
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
</style>
