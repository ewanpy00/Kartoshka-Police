<script setup lang="ts">
// The append-only evidence chain (each row stores the previous row's hash), checked link by link.
// Up to 48 blocks are drawn; with more records each block stands for a range of them.
import { computed } from 'vue'
import { t } from '../i18n'

export interface ChainResult { ok: boolean; rows: number; broken_at: number | null; checked_at: string }
const props = defineProps<{ chain: ChainResult | null; loading: boolean }>()

const MAX = 48
const count = computed(() => (props.chain ? Math.max(1, Math.min(MAX, props.chain.rows)) : 24))
const per = computed(() => (props.chain ? Math.max(1, Math.ceil(props.chain.rows / count.value)) : 1))
const brokenBlock = computed(() => {
  const c = props.chain
  if (!c || c.ok || c.broken_at === null) return -1
  return Math.min(count.value - 1, Math.max(0, Math.floor((c.broken_at - 1) / per.value)))
})

function state(i: number): string {
  if (props.loading || !props.chain) return 'wait'
  if (brokenBlock.value < 0) return 'ok'
  return i < brokenBlock.value ? 'ok' : i === brokenBlock.value ? 'bad' : 'cut'
}
</script>

<template>
  <div class="chain card" :class="loading ? 'loading' : chain?.ok ? 'good' : chain ? 'broken' : ''" role="status">
    <div class="row">
      <strong v-if="loading">{{ t('chain.verifying') }}</strong>
      <strong v-else-if="chain" :class="chain.ok ? 'okText' : 'badText'">{{ chain.ok ? t('chain.ok') : t('chain.broken') }}</strong>
      <span v-if="chain && !loading" class="muted small">{{ chain.rows }} {{ t('chain.records') }} · {{ new Date(chain.checked_at).toLocaleTimeString() }}
        <template v-if="!chain.ok && chain.broken_at !== null"> · #{{ chain.broken_at }}</template></span>
    </div>
    <div class="blocks" :key="chain?.checked_at ?? 'wait'">
      <template v-for="i in count" :key="i">
        <span class="block" :class="state(i - 1)" :style="{ animationDelay: `${(i - 1) * 30}ms` }" />
        <span v-if="i < count" class="link" :class="state(i - 1)" :style="{ animationDelay: `${(i - 1) * 30 + 15}ms` }" />
      </template>
    </div>
  </div>
</template>

<style scoped>
.chain { margin: 0.5rem 0 0.75rem; }
.chain.good { border-color: color-mix(in srgb, var(--allow) 45%, var(--line)); }
.chain.broken { border-color: var(--block); }
.okText { color: var(--allow); }
.badText { color: var(--block); }
.blocks { display: flex; flex-wrap: wrap; align-items: center; gap: 0; margin-top: 0.5rem; direction: ltr; }
.block { width: 0.85rem; height: 0.85rem; border-radius: 3px; border: 1px solid var(--line); background: var(--surface-2); }
.link { width: 0.45rem; height: 2px; background: var(--line); }
.block.wait { animation: kp-blink 1.1s ease-in-out infinite; }
.block.ok { animation: chain-ok 280ms var(--ease-out) both; }
.link.ok { animation: chain-link 200ms ease-out both; }
.block.bad { animation: chain-bad 520ms var(--ease-spring) both; }
.block.cut, .link.cut { opacity: 0.35; border-style: dashed; }
@keyframes chain-ok { from { background: var(--surface-2); transform: scale(0.7); } to { background: var(--allow); border-color: var(--allow); transform: scale(1); } }
@keyframes chain-link { to { background: var(--allow); } }
@keyframes chain-bad {
  0% { transform: scale(0.7); }
  40% { transform: scale(1.35) rotate(-8deg); }
  70% { transform: scale(1) rotate(6deg); }
  100% { background: var(--block); border-color: var(--block); transform: none; box-shadow: 0 0 0 4px var(--block-soft); }
}
</style>
