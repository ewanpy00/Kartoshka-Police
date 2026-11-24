<script setup lang="ts">
import { computed } from 'vue'

export interface SeriesPoint {
  label: string
  bars: number
  outlined: number
  line: number
}

const props = defineProps<{
  points: SeriesPoint[]
  barsLabel: string
  outlinedLabel: string
  lineLabel: string
  label: string
}>()

const W = 640
const H = 240
const PAD_L = 40
const PAD_R = 12
const PAD_T = 12
const PAD_B = 28
const plotW = W - PAD_L - PAD_R
const plotH = H - PAD_T - PAD_B

function niceMax(v: number): number {
  if (v <= 4) return Math.max(v, 1)
  const step = 10 ** Math.floor(Math.log10(v))
  return Math.ceil(v / step) * step
}

const yMax = computed(() =>
  niceMax(Math.max(1, ...props.points.flatMap((p) => [p.bars, p.outlined, p.line]))),
)

const ticks = computed(() => {
  const max = yMax.value
  const count = max < 4 ? max : 4
  return Array.from({ length: count + 1 }, (_, i) => {
    const value = (max * i) / count
    return { value: Number.isInteger(value) ? value : Math.round(value * 10) / 10, y: yFor(value) }
  })
})

function yFor(v: number): number {
  return PAD_T + plotH - (v / yMax.value) * plotH
}

const slot = computed(() => plotW / Math.max(props.points.length, 1))
const barW = computed(() => Math.max(Math.min(slot.value * 0.36, 24), 1))

function centre(i: number): number {
  return PAD_L + slot.value * (i + 0.5)
}

const labelEvery = computed(() => Math.max(1, Math.ceil(props.points.length / 8)))

const linePath = computed(() =>
  props.points.map((p, i) => `${i === 0 ? 'M' : 'L'}${centre(i)} ${yFor(p.line)}`).join(' '),
)
</script>

<template>
  <div class="series-chart">
    <svg :viewBox="`0 0 ${W} ${H}`" role="img" :aria-label="label" preserveAspectRatio="xMidYMid meet">
      <g v-for="tick in ticks" :key="tick.y">
        <line class="grid" :x1="PAD_L" :x2="W - PAD_R" :y1="tick.y" :y2="tick.y" />
        <text class="tick" :x="PAD_L - 6" :y="tick.y" text-anchor="end" dominant-baseline="middle">{{ tick.value }}</text>
      </g>
      <g v-for="(p, i) in points" :key="i">
        <rect
          class="mark-bars"
          :x="centre(i) - barW - 1"
          :y="yFor(p.bars)"
          :width="barW"
          :height="yFor(0) - yFor(p.bars)"
        />
        <rect
          class="mark-outlined"
          :x="centre(i) + 1"
          :y="yFor(p.outlined)"
          :width="barW"
          :height="yFor(0) - yFor(p.outlined)"
        />
        <text
          v-if="i % labelEvery === 0"
          class="tick"
          :x="centre(i)"
          :y="H - PAD_B + 16"
          text-anchor="middle"
        >{{ p.label }}</text>
      </g>
      <path class="mark-line" :d="linePath" />
      <circle v-for="(p, i) in points" :key="`c${i}`" class="mark-point" :cx="centre(i)" :cy="yFor(p.line)" r="3.5" />
    </svg>
    <ul class="legend">
      <li>
        <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><rect class="mark-bars" x="2" y="2" width="10" height="10" /></svg>
        {{ barsLabel }}
      </li>
      <li>
        <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><rect class="mark-outlined" x="2" y="2" width="10" height="10" /></svg>
        {{ outlinedLabel }}
      </li>
      <li>
        <svg width="22" height="14" viewBox="0 0 22 14" aria-hidden="true">
          <path class="mark-line" d="M1 7 H21" />
          <circle class="mark-point" cx="11" cy="7" r="3.5" />
        </svg>
        {{ lineLabel }}
      </li>
    </ul>
  </div>
</template>

<style scoped>
.series-chart > svg {
  display: block;
  direction: ltr;
  inline-size: 100%;
  block-size: auto;
}

.grid {
  stroke: var(--c-hairline);
  stroke-width: 1;
}

.tick {
  fill: var(--c-muted);
  font-size: var(--fs-12);
  font-variant-numeric: tabular-nums;
}

.mark-bars {
  fill: var(--c-amber);
}

.mark-outlined {
  fill: var(--c-surface);
  stroke: var(--c-muted);
  stroke-width: 1.5;
}

.mark-line {
  fill: none;
  stroke: var(--c-risk);
  stroke-width: 2;
  stroke-linejoin: round;
}

.mark-point {
  fill: var(--c-surface);
  stroke: var(--c-risk);
  stroke-width: 2;
}

.legend {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2) var(--space-4);
  margin: var(--space-2) 0 0;
  padding: 0;
  list-style: none;
  font-size: var(--fs-13);
  color: var(--c-muted);
}

.legend li {
  display: inline-flex;
  gap: 6px;
  align-items: center;
}
</style>
