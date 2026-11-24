<script setup lang="ts">
// What a confirmation sets in motion: the blocklist version moves and every client reads it on its next sync
// (DNS shield, Android Gatekeeper Bloom filter, the check API). It shows the publish, not a device count.
import { t } from '../i18n'

defineProps<{ version?: number | null; dense?: boolean }>()

const targets = [
  { key: 'prop.dns', icon: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Zm-7 9h14M12 3c2.5 2.6 3.7 5.6 3.7 9S14.5 18.4 12 21c-2.5-2.6-3.7-5.6-3.7-9S9.5 5.6 12 3Z' },
  { key: 'prop.android', icon: 'M8 3h8a1.5 1.5 0 0 1 1.5 1.5v15A1.5 1.5 0 0 1 16 21H8a1.5 1.5 0 0 1-1.5-1.5v-15A1.5 1.5 0 0 1 8 3Zm3 15h2' },
  { key: 'prop.api', icon: 'M12 3 5 6v5.5c0 4.2 3 8 7 9.5 4-1.5 7-5.3 7-9.5V6l-7-3Zm-3 9 2 2 4-4' },
] as const
</script>

<template>
  <div class="prop" :class="{ dense }" role="status">
    <div class="node done">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12.5 4.5 4.5L19 7.5" /></svg>
      {{ t('prop.officer') }}
    </div>
    <span class="wire w1" />
    <div class="node list">
      {{ t('prop.blocklist') }}
      <span v-if="version" class="ver"><s>v{{ version - 1 }}</s><b>v{{ version }}</b></span>
    </div>
    <span class="wire w2" />
    <div class="targets">
      <div v-for="(target, i) in targets" :key="target.key" class="node target" :style="{ animationDelay: `${900 + i * 160}ms` }">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path :d="target.icon" /></svg>
        {{ t(target.key) }}
      </div>
    </div>
    <p v-if="!dense" class="note small muted">{{ t('prop.note') }}</p>
  </div>
</template>

<style scoped>
.prop { display: grid; grid-template-columns: auto minmax(1.5rem, 1fr) auto minmax(1.5rem, 1fr) auto; align-items: center; gap: 0.4rem;
  padding: 0.6rem 0.75rem; border: 1px solid color-mix(in srgb, var(--block) 35%, var(--line)); border-radius: var(--radius);
  background: linear-gradient(90deg, var(--block-soft), var(--surface) 70%); animation: kp-rise var(--dur) var(--ease-out) both; }
.dense { padding: 0.4rem 0.5rem; gap: 0.3rem; font-size: 0.8rem; }
.node { display: inline-flex; align-items: center; gap: 0.3rem; padding: 0.2rem 0.5rem; border-radius: 6px; background: var(--surface);
  border: 1px solid var(--line); font-weight: 600; font-size: 0.82rem; white-space: nowrap; animation: kp-rise var(--dur) var(--ease-out) both; }
.dense .node { font-size: 0.72rem; padding: 0.1rem 0.35rem; }
.node svg { width: 1rem; height: 1rem; fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
.done { color: var(--allow); }
.list { color: var(--block); border-color: color-mix(in srgb, var(--block) 40%, var(--line)); animation-delay: 450ms; box-shadow: var(--glow-block); }
.ver { display: inline-flex; gap: 0.3rem; font-family: var(--mono); }
.ver s { color: var(--muted); animation: kp-blink 0.5s 700ms 2 both; }
.ver b { animation: kp-rise var(--dur) 800ms var(--ease-spring) both; }
.wire { height: 2px; background: linear-gradient(90deg, var(--allow), var(--block)); transform-origin: left; animation: kp-grow 380ms var(--ease-out) both; }
[dir='rtl'] .wire { transform-origin: right; }
.w1 { animation-delay: 150ms; }
.w2 { animation-delay: 650ms; }
.targets { display: grid; gap: 0.25rem; }
.target { color: var(--text); }
.note { grid-column: 1 / -1; margin: 0.1rem 0 0; }
/* Narrow columns (the live wall's side rail): one wrapped row instead of the fan. */
.dense { display: flex; flex-wrap: wrap; align-items: center; }
.dense .wire { width: 1rem; flex: none; }
.dense .w2 { display: none; }
.dense .targets { display: flex; flex-wrap: wrap; gap: 0.25rem; flex-basis: 100%; }
@media (max-width: 640px) {
  .prop:not(.dense) { grid-template-columns: 1fr; }
  .wire { width: 2px; height: 0.8rem; justify-self: center; }
}
</style>
