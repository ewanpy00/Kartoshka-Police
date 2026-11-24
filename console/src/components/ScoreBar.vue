<script setup lang="ts">
// The score as the sum it is (core/app/verdict/bands.py: score = clamp(sum of reason weights, 0, 100)).
// Each positive reason is one segment; hovering a segment or a reason row highlights the other.
import { computed } from 'vue'
import { lang, t } from '../i18n'
import type { Reason } from '../types'

const props = defineProps<{ reasons: Reason[]; score: number; verdict?: string | null; active?: string | null; big?: boolean }>()
const emit = defineEmits<{ 'update:active': [code: string | null] }>()

const positive = computed(() => props.reasons.filter((r) => (r.weight ?? 0) > 0))
const sum = computed(() => positive.value.reduce((total, r) => total + (r.weight ?? 0), 0))
const offset = computed(() => props.reasons.reduce((total, r) => total + Math.min(0, r.weight ?? 0), 0))
const scale = computed(() => Math.max(100, sum.value))
const band = computed(() => props.verdict && ['allow', 'warn', 'block'].includes(props.verdict)
  ? props.verdict : props.score > 70 ? 'block' : props.score >= 30 ? 'warn' : 'allow')

function group(reason: Reason): string {
  if (reason.source === 'ai' || reason.code === 'AI_ASSESSMENT') return 'ai'
  if (reason.source === 'sandbox') return 'deep'
  return 'fast'
}

function label(reason: Reason): string {
  return lang.value === 'ar' && reason.ar ? reason.ar : reason.en
}
</script>

<template>
  <div class="scorebar" :class="[band, { big }]">
    <div class="track" role="img" :aria-label="`score ${score} of 100`">
      <span
        v-for="(reason, i) in positive" :key="reason.code" class="seg"
        :class="[group(reason), { active: active === reason.code, dim: active && active !== reason.code }]"
        :style="{ width: `${((reason.weight ?? 0) / scale) * 100}%`, animationDelay: `${i * 70}ms` }"
        :title="`+${reason.weight} · ${label(reason)}`"
        @mouseenter="emit('update:active', reason.code)" @mouseleave="emit('update:active', null)"
      ><span v-if="(reason.weight ?? 0) / scale > 0.06" class="lbl">+{{ reason.weight }}</span></span>
      <i class="tick" :style="{ insetInlineStart: `${(30 / scale) * 100}%` }" />
      <i class="tick" :style="{ insetInlineStart: `${(70 / scale) * 100}%` }" />
    </div>
    <div class="legend small muted">
      <strong class="total">{{ score }}</strong><span>/100</span>
      <template v-if="sum > 100"> · {{ sum }} · {{ t('score.capped') }}</template>
      <template v-if="offset < 0"> · {{ offset }} {{ t('score.trust') }}</template>
    </div>
  </div>
</template>

<style scoped>
.scorebar { --c: var(--muted); margin: 0.35rem 0 0.6rem; }
.scorebar.block { --c: var(--block); }
.scorebar.warn { --c: var(--warn); }
.scorebar.allow { --c: var(--allow); }
.track { position: relative; display: flex; height: 0.9rem; border-radius: 999px; background: var(--surface-2); border: 1px solid var(--line); overflow: hidden; direction: ltr; }
[dir='rtl'] .track { direction: rtl; }
.big .track { height: 1.6rem; }
.seg {
  position: relative; display: grid; place-items: center; min-width: 3px; height: 100%;
  background: var(--c); box-shadow: inset -1px 0 0 rgb(0 0 0 / 0.25);
  transform-origin: left center; animation: kp-grow var(--dur-slow) var(--ease-out) both;
  transition: opacity var(--dur-fast) ease, filter var(--dur-fast) ease, width var(--dur-slow) var(--ease-out);
  cursor: default;
}
[dir='rtl'] .seg { transform-origin: right center; }
.seg.fast { opacity: 0.72; }
.seg.ai { background: var(--ai); }
.seg.dim { opacity: 0.28; }
.seg.active { opacity: 1; filter: brightness(1.15); }
.lbl { font-size: 0.66rem; font-weight: 700; color: var(--on-block); font-family: var(--mono); pointer-events: none; }
.big .lbl { font-size: 0.78rem; }
.tick { position: absolute; top: -2px; bottom: -2px; width: 0; border-inline-start: 1px dashed var(--muted); opacity: 0.6; pointer-events: none; }
.legend { margin-top: 0.25rem; }
.total { color: var(--c); font-size: 1.05rem; font-variant-numeric: tabular-nums; }
.big .total { font-size: 1.4rem; }
</style>
