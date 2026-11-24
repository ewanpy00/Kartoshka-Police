<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { checkHealth, type HealthResult } from './health'

const result = ref<HealthResult | null>(null)

async function refresh() {
  result.value = null
  result.value = await checkHealth()
}

onMounted(refresh)
</script>

<template>
  <main>
    <h1>Kartoshka-Police officer console</h1>
    <section class="card" :class="result?.state ?? 'loading'">
      <h2>Core API</h2>
      <p v-if="!result">Checking core...</p>
      <p v-else-if="result.state === 'unreachable'">
        Core is unreachable. Is the stack running?
      </p>
      <template v-else>
        <p v-if="result.state === 'healthy'">Core is healthy.</p>
        <p v-else>Core is degraded.</p>
        <dl>
          <dt>status</dt>
          <dd>{{ result.health.status }}</dd>
          <dt>db</dt>
          <dd>{{ result.health.db }}</dd>
          <dt>redis</dt>
          <dd>{{ result.health.redis }}</dd>
        </dl>
      </template>
    </section>
    <button :disabled="!result" @click="refresh">Check again</button>
  </main>
</template>

<style scoped>
.card {
  margin-bottom: 1rem;
  padding: 1rem 1.25rem;
  background: #fff;
  border-left: 0.375rem solid #9aa5b1;
  border-radius: 0.375rem;
}

.card.healthy {
  border-color: #2f9e44;
}

.card.degraded {
  border-color: #e8a317;
}

.card.unreachable {
  border-color: #d64545;
}

h2 {
  margin: 0 0 0.5rem;
  font-size: 1.1rem;
}

dl {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 0.25rem 1rem;
  margin: 0;
}

dt {
  color: #52606d;
}

dd {
  margin: 0;
  font-weight: 600;
}
</style>
