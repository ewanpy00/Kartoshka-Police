<script setup lang="ts">
// Link X-ray (ARCHITECTURE.md 3.1): source cards tick in ~150 ms apart. Timing is cosmetic; every card's
// final state comes from `sources[]` in the real response, and a source that was not queried is never green.
import { computed, onUnmounted, ref, watch } from 'vue'
import type { Source } from '../api'
import { SOURCE_NAMES, tr } from '../i18n'

const props = defineProps<{ sources: Source[] | null }>()
const ORDER = Object.keys(SOURCE_NAMES)
const shown = ref(0)
let timer: number | undefined

function tick() {
  window.clearInterval(timer)
  timer = window.setInterval(() => {
    if (shown.value >= ORDER.length) return window.clearInterval(timer)
    // the response is in: fast-forward
    shown.value += props.sources ? 2 : 1
    if (!props.sources && shown.value >= ORDER.length - 1) shown.value = ORDER.length - 2
  }, 150)
}
tick()
watch(() => props.sources, () => { if (props.sources) tick() })
onUnmounted(() => window.clearInterval(timer))

const cards = computed(() => ORDER.map((id, index) => {
  const source = props.sources?.find((s) => s.id === id)
  const visible = index < shown.value
  let state = 'waiting'
  if (visible && source) state = source.detail === 'running' ? 'running' : source.status
  else if (visible) state = 'checking'
  return { id, state, visible, detail: source?.detail }
}))

function label(state: string): string {
  return {
    hit: tr('Found', 'تم رصده'), clean: tr('Clean', 'سليم'), unknown: tr('No answer', 'لا إجابة'),
    skipped: tr('Not checked', 'لم يُفحص'), running: tr('Running…', 'جارٍ…'), checking: tr('Checking…', 'جارٍ الفحص…'),
  }[state] ?? ''
}
</script>

<template>
  <ul class="xray">
    <li v-for="card in cards" v-show="card.visible" :key="card.id" :class="card.state">
      <span class="dot" />
      <span class="name">{{ tr(SOURCE_NAMES[card.id][0], SOURCE_NAMES[card.id][1]) }}</span>
      <span class="state">{{ label(card.state) }}</span>
    </li>
  </ul>
</template>

<style scoped>
.xray { list-style: none; padding: 0; margin: 0 0 var(--space-3); display: grid; gap: var(--space-2); }
li { display: flex; align-items: center; gap: var(--space-3); background: var(--c-surface); border: 1px solid var(--c-hairline); border-radius: var(--radius-2);
  padding: var(--space-2) var(--space-3); animation: in 0.15s ease-out; font-size: var(--fs-14); }
@keyframes in { from { opacity: 0; transform: translateY(-4px); } }
.name { flex: 1; }
.state { font-size: var(--fs-12); color: var(--c-muted); }
.dot { width: 0.65rem; height: 0.65rem; border-radius: 50%; background: var(--c-muted); opacity: 0.5; }
.hit .dot { background: var(--c-risk); opacity: 1; } .hit .state { color: var(--c-risk); font-weight: 700; }
.clean .dot { background: var(--c-ok); opacity: 1; } .clean .state { color: var(--c-ok); }
.running .dot, .checking .dot { background: var(--c-accent); opacity: 1; animation: pulse 1s infinite; }
@keyframes pulse { 50% { opacity: 0.3; } }
</style>
