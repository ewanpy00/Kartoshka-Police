<script setup lang="ts">
// One case played through the engine's stages (ARCHITECTURE.md 1.1–1.4): discovered → normalised → fast score →
// sandbox → AI → verdict. Timing is presentation only; every value shown comes from the case record. If deep
// analysis is still running, the stage waits on the sandbox step until the deep verdict event arrives.
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { glyphs, hasLookalikes } from '../../defang'
import { lang, t } from '../../i18n'
import type { MessageKey } from '../../i18n/en'
import type { LiveSource } from '../../live/source'
import { reducedMotion, useCountUp } from '../../motion'
import type { CaseDetail, Reason } from '../../types'
import ScoreBar from '../ScoreBar.vue'
import ScoreRing from './ScoreRing.vue'

export interface FocusItem { key: string; domain: string; source: string; brand: string | null; rev: number; replay: boolean }

const props = defineProps<{ item: FocusItem; feed: LiveSource; paused: boolean }>()
const emit = defineEmits<{ done: [] }>()

const STAGES = ['discover', 'normalize', 'fast', 'sandbox', 'ai', 'verdict'] as const
const AT = [0, 700, 1500, 3000, 4700, 6200]
const HOLD = 6500
const WAIT_DEEP = 20_000
const WAIT_LOAD = 8_000
const SANDBOX_GATE = AT[3] + 800

const detail = ref<CaseDetail | null>(null)
const elapsed = ref(0)
let waitedDeep = 0
let waitedLoad = 0
let finished = false
let timer = 0

const latest = computed(() => detail.value?.latest ?? null)
const deepReady = computed(() => !!latest.value && !['queued', 'running', 'joined'].includes(latest.value.deep_status ?? ''))
const phase = computed(() => AT.filter((x) => elapsed.value >= x).length - 1)
const waiting = computed(() => phase.value === 3 && !deepReady.value)

async function load() {
  const next = await props.feed.caseDetail(props.item.domain)
  if (next) detail.value = next
}

watch(() => props.item.key, () => {
  detail.value = null
  elapsed.value = 0
  waitedDeep = 0
  waitedLoad = 0
  finished = false
  load()
}, { immediate: true })
watch(() => props.item.rev, load)

function finish() {
  finished = true
  emit('done')
}

function tick() {
  if (props.paused || finished) return
  if (!detail.value) {
    waitedLoad += 100
    if (waitedLoad > WAIT_LOAD) finish()
    return
  }
  if (reducedMotion.value && elapsed.value < AT[5]) {
    if (deepReady.value || waitedDeep > WAIT_DEEP) elapsed.value = AT[5]
    else {
      elapsed.value = AT[3]
      waitedDeep += 100
    }
    return
  }
  if (elapsed.value === SANDBOX_GATE && !deepReady.value && waitedDeep < WAIT_DEEP) {
    waitedDeep += 100
    return
  }
  elapsed.value += 100
  if (elapsed.value >= AT[5] + HOLD) finish()
}

onMounted(() => { timer = window.setInterval(tick, 100) })
onBeforeUnmount(() => window.clearInterval(timer))

function group(reason: Reason): number {
  if (reason.source === 'ai' || reason.code === 'AI_ASSESSMENT') return 4
  return reason.source === 'sandbox' ? 3 : 2
}
const shownReasons = computed(() => (latest.value?.reasons ?? [])
  .filter((reason) => group(reason) <= phase.value && (group(reason) < 3 || deepReady.value)))
const runningScore = computed(() => {
  if (!latest.value || phase.value < 2) return 0
  if (phase.value >= 5) return latest.value.score
  return Math.max(0, Math.min(100, shownReasons.value.reduce((total, reason) => total + (reason.weight ?? 0), 0)))
})

const chips = computed(() => (latest.value?.sources ?? []).map((source, i) => {
  const step = source.id === 'ai' ? 4 : source.id === 'sandbox' ? 3 : 2
  const pending = step >= 3 && !deepReady.value
  return { ...source, shown: phase.value >= step, pending, delay: step === 2 ? i * 90 : 0 }
}))

const display = computed(() => detail.value?.display ?? props.item.domain.replace(/\./g, '[.]'))
const chars = computed(() => {
  const out: { c: string; odd: boolean; title?: string }[] = []
  for (const part of glyphs(display.value)) {
    if (part.odd) out.push({ c: part.text, odd: true, title: part.title })
    else for (const c of part.text) out.push({ c, odd: false })
  }
  return out
})
const flags = computed(() => {
  const list: { text: string; bad: boolean }[] = []
  if (hasLookalikes(display.value)) list.push({ text: 'mixed scripts', bad: true })
  if (props.item.domain.includes('xn--')) list.push({ text: 'punycode', bad: true })
  const l = latest.value
  if (l?.display_final_url && l.display_final_url !== l.display_url) list.push({ text: 'redirects', bad: true })
  if (l?.brand) list.push({ text: l.brand, bad: false })
  return list
})

const aiText = computed(() => {
  const l = latest.value
  if (!l) return ''
  const reason = l.reasons.find((r) => r.code === 'AI_ASSESSMENT')
  const source = l.sources.find((s) => s.id === 'ai')
  const fromReason = reason ? (lang.value === 'ar' && reason.ar ? reason.ar : reason.en) : ''
  const text = source?.detail && source.detail.length > 12 ? source.detail : fromReason
  return text.replace(/^AI review:\s*/i, '')
})
const typed = computed(() => {
  if (phase.value < 4) return ''
  const count = reducedMotion.value ? aiText.value.length : Math.floor((elapsed.value - AT[4]) / 16)
  return aiText.value.slice(0, count)
})

const shot = computed(() => (detail.value ? props.feed.screenshot(detail.value) : null))
const page = computed(() => (deepReady.value && phase.value >= 3 ? detail.value?.page ?? null : null))
const FIELD: Record<string, string> = {
  otp: 'One-time code', card: 'Card number', cvv: 'CVV', uaepass: 'Emirates ID / UAE PASS', emirates_id: 'Emirates ID',
  password: 'Password', iban: 'IBAN',
}
const fields = computed(() => {
  const asks = page.value?.asks_for ?? []
  const list = asks.map((a) => FIELD[a] ?? a)
  if (!list.length && page.value) return []
  return list.length ? list : ['Username', 'Password']
})
const visualPct = useCountUp(() => (phase.value >= 3 && deepReady.value && detail.value?.visual ? Math.round(detail.value.visual.similarity * 100) : 0), 1200)

const verdict = computed(() => latest.value?.verdict ?? 'pending')
const verdictLabel = computed(() => {
  const key = `status.${verdict.value}` as MessageKey
  const translated = t(key)
  return translated === key ? verdict.value : translated
})
const safe = computed(() => {
  const action = latest.value?.safe_action
  if (!action) return ''
  return (lang.value === 'ar' ? action.label_ar : action.label_en) ?? action.label_en ?? ''
})
</script>

<template>
  <section class="stage" :class="[phase >= 5 ? `final ${verdict}` : '', { waiting }]">
    <ol class="rail">
      <li v-for="(name, i) in STAGES" :key="name" :class="{ done: phase > i || (phase === 5 && i === 5), on: phase === i && phase < 5 }">
        <span class="node"><i /></span>
        <span class="name">{{ t(`stage.${name}` as MessageKey) }}</span>
      </li>
      <span class="fill" :style="{ transform: `scaleX(${Math.min(phase, 5) / 5})` }" />
    </ol>

    <div class="body">
      <div class="main">
        <div class="meta">
          <span class="src">{{ item.source }}</span>
          <span v-if="item.replay" class="tag">{{ t('live.replay') }}</span>
          <span v-if="latest?.brand" class="tag brand">{{ latest.brand }}</span>
        </div>
        <h2 class="domain" :key="item.key" dir="ltr">
          <template v-for="(ch, i) in chars" :key="i"><mark v-if="ch.odd" class="glyph ch" :title="ch.title" :style="{ animationDelay: `${i * 22}ms` }">{{ ch.c }}</mark><span v-else class="ch" :style="{ animationDelay: `${i * 22}ms` }">{{ ch.c }}</span></template>
        </h2>
        <p v-if="latest" class="url mono" dir="ltr">{{ latest.display_url }}<template v-if="latest.display_final_url && latest.display_final_url !== latest.display_url"> → {{ latest.display_final_url }}</template></p>
        <div class="flags" :class="{ shown: phase >= 1 }">
          <span v-for="flag in flags" :key="flag.text" class="flag" :class="{ bad: flag.bad }">{{ flag.text }}</span>
        </div>

        <div class="scorebox">
          <ScoreRing :value="runningScore" :label="phase >= 5 ? verdictLabel : 'score'" />
          <div class="scorebar-wrap">
            <ScoreBar v-if="latest" :reasons="shownReasons" :score="runningScore" big />
            <ul class="reasons">
              <TransitionGroup name="row">
                <li v-for="reason in shownReasons" :key="reason.code" :class="`g${group(reason)}`">
                  <b>+{{ reason.weight ?? 0 }}</b> {{ lang === 'ar' && reason.ar ? reason.ar : reason.en }}
                </li>
              </TransitionGroup>
            </ul>
          </div>
        </div>

        <div class="chips">
          <span
            v-for="chip in chips" :key="chip.id" class="chip" :class="[chip.pending ? 'pending' : chip.status, { shown: chip.shown }]"
            :style="{ transitionDelay: `${chip.delay}ms` }" :title="chip.detail ?? ''"
          >
            <i />{{ chip.id }}<small v-if="chip.detail && !chip.pending">{{ chip.detail }}</small><small v-else-if="chip.pending">…</small>
          </span>
        </div>

        <p class="ailine" :class="{ shown: phase >= 4 && aiText }">
          <span class="badge ai">AI</span> <span dir="auto">{{ typed }}</span><span v-if="phase === 4" class="caret" />
        </p>
      </div>

      <aside class="side">
        <div class="phone" :class="{ scanning: phase === 3 || waiting }">
          <div class="notch" />
          <div class="screen">
            <img v-if="shot && phase >= 3 && deepReady" :src="shot" alt="Sandbox screenshot of the page" />
            <div v-else-if="page && feed.demo" class="wire">
              <div class="bar" />
              <p class="wt">{{ page.title }}</p>
              <label v-for="field in fields" :key="field" class="field" :class="{ hot: field !== 'Username' }"><span>{{ field }}</span><i /></label>
              <div v-if="fields.length" class="btn">Continue</div>
              <p v-else class="parked">· · ·</p>
            </div>
            <p v-else-if="phase >= 3" class="cap">{{ waiting ? t('live.capturing') : t('live.nocapture') }}</p>
          </div>
          <div class="scan" />
        </div>
        <div v-if="page?.asks_for?.length" class="asks">
          <span class="muted small">{{ t('live.asks') }}</span>
          <span v-for="(a, i) in page.asks_for" :key="a" class="ask" :style="{ animationDelay: `${i * 140}ms` }">{{ a }}</span>
        </div>
        <div v-if="detail?.visual && page" class="looks">
          <span class="muted small">{{ t('live.looks') }} {{ detail.visual.brand_id }}</span>
          <b>{{ visualPct }}%</b>
          <span class="meter"><i :style="{ width: `${visualPct}%` }" /></span>
        </div>
      </aside>
    </div>

    <div v-if="phase >= 5" class="stamp" :class="verdict">
      <b>{{ verdictLabel }}</b><span>{{ latest?.score }}</span>
    </div>
    <p v-if="phase >= 5 && safe" class="safe"><span class="muted small">{{ t('live.safe') }}</span> {{ safe }}</p>
  </section>
</template>

<style scoped>
.stage { position: relative; display: grid; gap: 1.1rem; padding: 1.25rem 1.4rem 1.4rem; border: 1px solid var(--line); border-radius: 14px;
  background: radial-gradient(120% 80% at 0% 0%, color-mix(in srgb, var(--accent) 10%, transparent), transparent 60%), var(--surface);
  transition: box-shadow 500ms ease, border-color 500ms ease; overflow: hidden; }
.stage.final.block { border-color: color-mix(in srgb, var(--block) 60%, var(--line)); box-shadow: 0 0 0 1px var(--block), 0 0 60px -10px var(--block); animation: flash-block 900ms ease-out; }
.stage.final.warn { border-color: color-mix(in srgb, var(--warn) 60%, var(--line)); box-shadow: 0 0 50px -14px var(--warn); }
.stage.final.allow { border-color: var(--allow); }
@keyframes flash-block { 0% { background-color: color-mix(in srgb, var(--block) 25%, var(--surface)); } 100% { background-color: var(--surface); } }

.rail { position: relative; display: grid; grid-template-columns: repeat(6, 1fr); list-style: none; margin: 0; padding: 0; }
.rail::before, .fill { content: ''; position: absolute; top: 0.6rem; inset-inline: 8.3%; height: 2px; background: var(--line); }
.fill { background: linear-gradient(90deg, var(--accent), var(--block)); transform-origin: left; transition: transform 600ms var(--ease-out); }
[dir='rtl'] .fill { transform-origin: right; }
.rail li { position: relative; z-index: 1; display: grid; justify-items: center; gap: 0.35rem; }
.node { width: 1.25rem; height: 1.25rem; border-radius: 50%; background: var(--surface); border: 2px solid var(--line); display: grid; place-items: center; transition: border-color 300ms, background 300ms; }
.node i { width: 0.45rem; height: 0.45rem; border-radius: 50%; background: transparent; transition: background 300ms; }
.rail li.done .node { border-color: var(--accent); background: var(--accent); }
.rail li.on .node { border-color: var(--accent); box-shadow: 0 0 0 0 var(--accent); animation: node-pulse 1.1s ease-out infinite; }
.rail li.on .node i { background: var(--accent); }
.name { font-size: 0.72rem; letter-spacing: 0.06em; text-transform: uppercase; color: var(--muted); text-align: center; }
.rail li.on .name, .rail li.done .name { color: var(--text); }
@keyframes node-pulse { from { box-shadow: 0 0 0 0 color-mix(in srgb, var(--accent) 60%, transparent); } to { box-shadow: 0 0 0 12px transparent; } }

.body { display: grid; grid-template-columns: minmax(0, 1fr) 15rem; gap: 1.4rem; align-items: start; }
@media (max-width: 1100px) { .body { grid-template-columns: minmax(0, 1fr); } .side { justify-self: center; } }
.meta { display: flex; gap: 0.4rem; align-items: center; }
.src { font-family: var(--mono); font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.12em; color: var(--accent); }
.tag { font-size: 0.7rem; padding: 0.05rem 0.45rem; border-radius: 999px; border: 1px solid var(--line); color: var(--muted); }
.tag.brand { color: var(--warn); border-color: color-mix(in srgb, var(--warn) 50%, var(--line)); }
.domain { margin: 0.25rem 0 0.15rem; font-family: var(--mono); font-size: clamp(1.4rem, 2.8vw, 2.4rem); font-weight: 700; letter-spacing: -0.01em; overflow-wrap: anywhere; line-height: 1.15; text-align: start; }
.ch { display: inline-block; animation: char-in 380ms var(--ease-out) both; }
@keyframes char-in { from { opacity: 0; transform: translateY(0.4em); filter: blur(4px); } to { opacity: 1; transform: none; filter: none; } }
mark.glyph.ch { font-size: inherit; }
.url { margin: 0; color: var(--muted); font-size: 0.8rem; overflow-wrap: anywhere; }
.flags { display: flex; gap: 0.35rem; flex-wrap: wrap; min-height: 1.4rem; margin-top: 0.5rem; opacity: 0; transform: translateY(4px); transition: opacity 300ms, transform 300ms var(--ease-out); }
.flags.shown { opacity: 1; transform: none; }
.flag { font-size: 0.72rem; padding: 0.1rem 0.5rem; border-radius: 4px; background: var(--surface-2); border: 1px solid var(--line); }
.flag.bad { color: var(--block); border-color: color-mix(in srgb, var(--block) 45%, var(--line)); background: var(--block-soft); }

.scorebox { display: flex; gap: 1.25rem; align-items: center; margin-top: 1rem; }
@media (max-width: 640px) { .scorebox { flex-direction: column; align-items: stretch; } }
.scorebar-wrap { flex: 1; min-width: 0; }
.reasons { list-style: none; padding: 0; margin: 0.3rem 0 0; display: grid; gap: 0.2rem; font-size: 0.86rem; }
.reasons b { display: inline-block; min-width: 2.4rem; font-family: var(--mono); color: var(--warn); }
.reasons .g3 b { color: var(--block); }
.reasons .g4 b { color: var(--ai); }

.chips { display: flex; flex-wrap: wrap; gap: 0.35rem; margin-top: 1rem; }
.chip { display: inline-flex; align-items: center; gap: 0.35rem; padding: 0.22rem 0.55rem; border-radius: 6px; font-family: var(--mono); font-size: 0.74rem;
  border: 1px solid var(--line); background: var(--surface-2); color: var(--muted); opacity: 0.15; transform: scale(0.92); transition: opacity 260ms, transform 260ms var(--ease-spring), border-color 260ms, color 260ms; }
.chip.shown { opacity: 1; transform: none; }
.chip i { width: 0.45rem; height: 0.45rem; border-radius: 50%; background: var(--muted); }
.chip small { color: var(--muted); font-size: 0.68rem; max-width: 24ch; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.chip.hit { color: var(--text); border-color: color-mix(in srgb, var(--block) 60%, var(--line)); }
.chip.hit.shown { box-shadow: 0 0 14px -4px var(--block); }
.chip.hit i { background: var(--block); box-shadow: 0 0 6px var(--block); }
.chip.clean i { background: var(--allow); }
.chip.unknown i { background: var(--warn); }
.chip.skipped { opacity: 0.45; }
.chip.pending.shown i { background: transparent; border: 2px solid var(--accent); border-top-color: transparent; animation: kp-spin 0.8s linear infinite; }

.ailine { margin: 0.9rem 0 0; min-height: 1.5rem; font-size: 0.92rem; opacity: 0; transition: opacity 300ms; }
.ailine.shown { opacity: 1; }
.caret { display: inline-block; width: 0.5em; height: 1em; vertical-align: -0.15em; background: var(--ai); margin-inline-start: 2px; animation: kp-blink 0.8s steps(1) infinite; }

.side { display: grid; gap: 0.7rem; justify-items: center; }
.phone { position: relative; width: 13rem; aspect-ratio: 9 / 18.5; border-radius: 1.8rem; padding: 0.55rem; background: #05070a; border: 1px solid var(--line);
  box-shadow: 0 20px 50px -20px rgb(0 0 0 / 0.8), inset 0 0 0 2px #1b2330; overflow: hidden; }
.notch { position: absolute; top: 0.55rem; left: 50%; width: 3.6rem; height: 0.9rem; transform: translateX(-50%); background: #05070a; border-radius: 0 0 0.6rem 0.6rem; z-index: 2; }
.screen { width: 100%; height: 100%; border-radius: 1.3rem; background: #0e141c; overflow: hidden; display: grid; place-items: center; }
.screen img { width: 100%; height: 100%; object-fit: cover; object-position: top; animation: kp-rise 500ms var(--ease-out) both; }
.cap { color: #8a97a8; font-size: 0.75rem; padding: 1rem; text-align: center; }
.scan { position: absolute; inset-inline: 0.55rem; top: 0; height: 30%; pointer-events: none; opacity: 0;
  background: linear-gradient(180deg, transparent, color-mix(in srgb, var(--accent) 45%, transparent) 85%, var(--accent)); }
.phone.scanning .scan { opacity: 1; animation: scan 1.6s ease-in-out infinite; }
@keyframes scan { from { transform: translateY(-100%); } to { transform: translateY(340%); } }
.wire { width: 100%; height: 100%; background: #f4f6f8; padding: 1.6rem 0.9rem 0.9rem; display: grid; align-content: start; gap: 0.55rem; color: #1c2430; animation: kp-rise 500ms var(--ease-out) both; }
.wire .bar { height: 0.5rem; width: 45%; border-radius: 3px; background: #c5ccd6; }
.wt { margin: 0.4rem 0 0.2rem; font-weight: 700; font-size: 0.95rem; }
.field { display: grid; gap: 0.2rem; font-size: 0.62rem; color: #5f6b7a; }
.field i { height: 1.5rem; border-radius: 5px; border: 1px solid #c5ccd6; background: #fff; }
.field.hot i { border-color: #ff5a4e; box-shadow: 0 0 0 2px rgb(255 90 78 / 0.25); animation: kp-pulse 1.2s 2; }
.btn { margin-top: 0.3rem; height: 1.7rem; border-radius: 6px; background: #3b4656; color: #fff; display: grid; place-items: center; font-size: 0.7rem; font-weight: 600; }
.parked { text-align: center; color: #9aa3ae; font-size: 1.2rem; margin-top: 3rem; }
.asks { display: flex; flex-wrap: wrap; gap: 0.3rem; align-items: center; justify-content: center; }
.ask { padding: 0.1rem 0.5rem; border-radius: 999px; background: var(--block); color: var(--on-block); font-size: 0.72rem; font-weight: 700; text-transform: uppercase; animation: ask-pop 420ms var(--ease-spring) both; }
@keyframes ask-pop { from { transform: scale(0.3); opacity: 0; } to { transform: none; opacity: 1; } }
.looks { width: 100%; display: grid; grid-template-columns: 1fr auto; gap: 0.2rem 0.5rem; align-items: center; }
.looks b { font-size: 1.3rem; color: var(--block); font-variant-numeric: tabular-nums; }
.meter { grid-column: 1 / -1; height: 0.35rem; border-radius: 999px; background: var(--line); overflow: hidden; }
.meter i { display: block; height: 100%; background: linear-gradient(90deg, var(--warn), var(--block)); }

.stamp { position: absolute; top: 4.2rem; inset-inline-end: 1.4rem; display: grid; justify-items: center; padding: 0.35rem 1rem; border: 3px solid currentColor; border-radius: 8px;
  color: var(--muted); transform: rotate(-8deg); animation: stamp 520ms var(--ease-spring) both; z-index: 5; background: color-mix(in srgb, var(--surface) 70%, transparent); backdrop-filter: blur(2px); pointer-events: none; }
.stamp b { font-size: 1.9rem; letter-spacing: 0.14em; text-transform: uppercase; line-height: 1; }
.stamp span { font-family: var(--mono); font-size: 0.85rem; }
.stamp.block { color: var(--block); text-shadow: 0 0 18px var(--block); }
.stamp.warn { color: var(--warn); }
.stamp.allow { color: var(--allow); }
@keyframes stamp { 0% { opacity: 0; transform: rotate(-8deg) scale(2.4); } 60% { opacity: 1; transform: rotate(-8deg) scale(0.92); } 100% { transform: rotate(-8deg) scale(1); } }
@media (max-width: 1100px) {
  .stamp { position: static; justify-self: center; order: -1; }
}
@media (max-width: 640px) {
  .stage { padding: 1rem; }
  .name { display: none; }
  .rail li.on .name { display: block; position: absolute; top: 1.6rem; white-space: nowrap; }
  .rail { margin-bottom: 1.2rem; }
}
.safe { margin: 0; padding: 0.5rem 0.75rem; border-radius: 8px; background: var(--allow-soft); color: var(--allow); font-weight: 600; animation: kp-rise 400ms 300ms var(--ease-out) both; }
.safe .muted { margin-inline-end: 0.5rem; }
</style>
