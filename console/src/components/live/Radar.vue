<script setup lang="ts">
// Certificate Transparency radar: every Hunter candidate is a blip that pings and fades.
// The angle comes from a hash of the name, so the same domain always lands in the same place.
export interface Blip { id: string; domain: string; band: 'cand' | 'warn' | 'block' }
defineProps<{ blips: Blip[] }>()

function hash(value: string): number {
  let h = 2166136261
  for (let i = 0; i < value.length; i++) h = Math.imul(h ^ value.charCodeAt(i), 16777619)
  return (h >>> 0) / 4294967295
}
function pos(domain: string): { x: number; y: number } {
  const a = hash(domain) * Math.PI * 2
  const r = 22 + hash(`${domain}#r`) * 64
  return { x: 100 + Math.cos(a) * r, y: 100 + Math.sin(a) * r }
}
</script>

<template>
  <div class="radar" aria-hidden="true">
    <div class="sweep" />
    <svg viewBox="0 0 200 200">
      <circle v-for="r in [30, 55, 80, 96]" :key="r" class="grid" cx="100" cy="100" :r="r" />
      <path class="grid" d="M100 4v192M4 100h192" />
      <g v-for="blip in blips" :key="blip.id" class="blip" :class="blip.band" :transform="`translate(${pos(blip.domain).x} ${pos(blip.domain).y})`">
        <circle class="ping" r="3" />
        <circle class="dot" r="2.6" />
      </g>
    </svg>
  </div>
</template>

<style scoped>
.radar { position: relative; width: 100%; max-width: 15rem; aspect-ratio: 1; margin: 0 auto; border-radius: 50%;
  background: radial-gradient(circle, color-mix(in srgb, var(--accent) 10%, transparent), transparent 70%); border: 1px solid var(--line); overflow: hidden; }
.sweep { position: absolute; inset: 0; border-radius: 50%; animation: kp-spin 4s linear infinite;
  background: conic-gradient(from 0deg, color-mix(in srgb, var(--accent) 45%, transparent), transparent 18%, transparent); }
svg { position: absolute; inset: 0; width: 100%; height: 100%; }
.grid { fill: none; stroke: var(--accent); stroke-opacity: 0.18; stroke-width: 0.6; }
.blip { animation: blip-life 16s linear forwards; }
.dot { fill: var(--warn); filter: drop-shadow(0 0 3px var(--warn)); }
.ping { fill: none; stroke: var(--warn); stroke-width: 1; animation: blip-ping 1.6s ease-out 2; transform-box: fill-box; transform-origin: center; }
.blip.cand .dot { fill: var(--accent); filter: drop-shadow(0 0 3px var(--accent)); }
.blip.cand .ping { stroke: var(--accent); }
.blip.block .dot { fill: var(--block); filter: drop-shadow(0 0 4px var(--block)); }
.blip.block .ping { stroke: var(--block); animation-iteration-count: infinite; }
@keyframes blip-ping { from { transform: scale(1); opacity: 1; } to { transform: scale(5); opacity: 0; } }
@keyframes blip-life { 0%, 70% { opacity: 1; } 100% { opacity: 0; } }
</style>
