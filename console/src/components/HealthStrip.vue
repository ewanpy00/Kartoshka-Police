<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { get } from '../api'
import type { AdminHealth } from '../types'

const health = ref<AdminHealth | null>(null)
const failed = ref(false)
let timer: number | undefined

async function load() {
  try {
    health.value = await get<AdminHealth>('/v1/admin/health')
    failed.value = false
  } catch {
    failed.value = true
  }
}

const items = computed(() => {
  const h = health.value
  if (!h) return []
  const hunterFresh = Object.values(h.hunter).some((s) => Date.now() - Date.parse(s.last) < 15 * 60_000)
  return [
    { label: 'redis', ok: h.redis === 'ok' },
    { label: `deep ${h.deep_queue?.waiting ?? '?'}`, ok: (h.deep_queue?.workers ?? 0) > 0 && h.checks.deep_stale === 0 },
    { label: 'hunter', ok: hunterFresh },
    { label: 'ai', ok: h.ai === 'configured' },
  ]
})

onMounted(() => {
  load()
  timer = window.setInterval(load, 30_000)
})
onUnmounted(() => window.clearInterval(timer))
</script>

<template>
  <RouterLink :to="{ name: 'health' }" class="strip">
    <span v-if="failed" class="dot bad">core unreachable</span>
    <span v-for="item in items" :key="item.label" class="dot" :class="item.ok ? 'ok' : 'bad'">{{ item.label }}</span>
  </RouterLink>
</template>

<style scoped>
.strip { display: flex; gap: 0.6rem; text-decoration: none; font-size: 0.78rem; color: var(--muted); }
.dot::before { content: ''; display: inline-block; width: 0.5rem; height: 0.5rem; border-radius: 50%; margin-inline-end: 0.25rem; background: var(--muted); }
.dot.ok::before { background: var(--allow); }
.dot.bad::before { background: var(--block); }
</style>
