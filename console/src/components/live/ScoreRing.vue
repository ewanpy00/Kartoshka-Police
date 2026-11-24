<script setup lang="ts">
// The score as a dial that climbs, changing colour as it crosses the warn (30) and block (>70) lines.
import { computed } from 'vue'
import { useCountUp } from '../../motion'

const props = defineProps<{ value: number; label?: string }>()
const shown = useCountUp(() => props.value, 1100)
const R = 52
const C = 2 * Math.PI * R
const band = computed(() => (shown.value > 70 ? 'block' : shown.value >= 30 ? 'warn' : 'allow'))
</script>

<template>
  <div class="ring" :class="band">
    <svg viewBox="0 0 120 120" aria-hidden="true">
      <circle class="bg" cx="60" cy="60" :r="R" />
      <circle class="tick" cx="60" cy="60" :r="R" :stroke-dasharray="`0 ${C * 0.3} 1.2 ${C * 0.4 - 1.2} 1.2 ${C}`" />
      <circle class="fg" cx="60" cy="60" :r="R" :stroke-dasharray="C" :stroke-dashoffset="C * (1 - shown / 100)" />
    </svg>
    <div class="value"><b>{{ shown }}</b><span v-if="label">{{ label }}</span></div>
  </div>
</template>

<style scoped>
.ring { --c: var(--allow); position: relative; width: 9.5rem; aspect-ratio: 1; flex: none; }
.ring.warn { --c: var(--warn); }
.ring.block { --c: var(--block); }
svg { width: 100%; height: 100%; transform: rotate(-90deg); overflow: visible; }
circle { fill: none; stroke-width: 9; }
.bg { stroke: var(--line); }
.tick { stroke: var(--muted); stroke-width: 13; opacity: 0.5; }
.fg { stroke: var(--c); stroke-linecap: round; filter: drop-shadow(0 0 6px color-mix(in srgb, var(--c) 70%, transparent)); transition: stroke 300ms ease; }
.value { position: absolute; inset: 0; display: grid; place-content: center; text-align: center; }
.value b { font-size: 2.7rem; line-height: 1; color: var(--c); font-variant-numeric: tabular-nums; transition: color 300ms ease; }
.value span { font-size: 0.72rem; letter-spacing: 0.12em; text-transform: uppercase; color: var(--muted); margin-top: 0.2rem; }
</style>
