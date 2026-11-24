<script setup lang="ts">
// Live operations wall (/live): the CT radar and Hunter feed on the left, the current case played through
// the engine's stages in the middle, officer decisions and their effect on the right. Built for a big screen
// and for the pitch; `?demo=1` swaps in a scripted scenario that is labelled as demo data.
import { computed, onBeforeUnmount, onMounted, ref, shallowRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { LiveEvent } from '../api'
import DefangedDomain from '../components/DefangedDomain.vue'
import Propagation from '../components/Propagation.vue'
import LiveStage, { type FocusItem } from '../components/live/LiveStage.vue'
import Radar, { type Blip } from '../components/live/Radar.vue'
import { defang } from '../defang'
import { lang, t, toggleLang } from '../i18n'
import { createDemoSource } from '../live/demo'
import { realSource, type LiveSource, type ReplayItem } from '../live/source'
import { useCountUp } from '../motion'
import { cycleTheme, dark, theme } from '../theme'

interface Candidate { id: string; domain: string; source: string; brand: string | null; at: number; band: 'cand' | 'warn' | 'block'; score: number | null }
interface Entry { id: string; kind: string; domain: string; text: string; tone: 'block' | 'allow' | 'warn' | 'info'; at: number; propagate: boolean }

const route = useRoute()
const router = useRouter()
const feed: LiveSource = route.query.demo !== undefined ? createDemoSource() : realSource

const connected = ref(feed.demo)
const paused = ref(false)
const candidates = ref<Candidate[]>([])
const blips = ref<Blip[]>([])
const queue = ref<FocusItem[]>([])
const current = ref<FocusItem | null>(null)
const entries = ref<Entry[]>([])
const spike = ref<{ brand: string; count: number } | null>(null)
const totals = ref({ candidates: 0, threats: 0, confirmed: 0, blocklist: 0 })
const replays = shallowRef<ReplayItem[]>([])
const now = ref(Date.now())

const shownCandidates = useCountUp(() => totals.value.candidates)
const shownThreats = useCountUp(() => totals.value.threats)
const shownConfirmed = useCountUp(() => totals.value.confirmed)
const shownBlocklist = useCountUp(() => totals.value.blocklist)

const seenChecks = new Set<string>()
let seq = 0
let idleSince = Date.now()
let replayIndex = 0
let spikeTimer = 0
const timers: number[] = []
let stop: (() => void) | undefined

const uid = () => `${Date.now().toString(36)}-${++seq}`
const str = (value: unknown) => (value === undefined || value === null ? '' : String(value))

function enqueue(event: LiveEvent) {
  const domain = str(event.domain)
  if (!domain) return
  if (current.value?.domain === domain) {
    current.value = { ...current.value, rev: current.value.rev + 1 }
    return
  }
  if (queue.value.some((item) => item.domain === domain)) return
  const item: FocusItem = { key: `${domain}#${uid()}`, domain, source: str(event.source) || 'check', brand: str(event.brand) || null, rev: 0, replay: false }
  if (!current.value || current.value.replay) {
    current.value = item
    return
  }
  queue.value = [...queue.value, item].slice(-6)
}

function log(entry: Omit<Entry, 'id' | 'at'>) {
  entries.value = [{ ...entry, id: uid(), at: Date.now() }, ...entries.value].slice(0, 12)
}

function onLive(event: LiveEvent) {
  idleSince = Date.now()
  switch (event.type) {
    case 'hello':
      connected.value = true
      break
    case 'hunter.candidate': {
      const domain = str(event.domain)
      const id = uid()
      candidates.value = [{ id, domain, source: str(event.source), brand: str(event.brand_id) || null, at: Date.now(), band: 'cand' as const, score: null },
        ...candidates.value].slice(0, 40)
      blips.value = [...blips.value, { id, domain, band: event.brand_id ? 'warn' as const : 'cand' as const }].slice(-40)
      totals.value.candidates += 1
      break
    }
    case 'check.verdict': {
      const check = str(event.check_id)
      if (check && !seenChecks.has(check)) {
        seenChecks.add(check)
        totals.value.threats += 1
      }
      const band = event.verdict === 'block' ? 'block' : 'warn'
      candidates.value.filter((c) => c.domain === event.domain).forEach((c) => { c.band = band; c.score = Number(event.score) })
      blips.value.filter((b) => b.domain === event.domain).forEach((b) => { b.band = band })
      enqueue(event)
      break
    }
    case 'case.reviewed': {
      const confirm = event.decision === 'confirm'
      if (confirm) {
        totals.value.confirmed += 1
        totals.value.blocklist += 1
      }
      entries.value = entries.value.map((e) => ({ ...e, propagate: false }))
      log({ kind: 'review', domain: str(event.domain), text: confirm ? t('live.confirm') : t('live.reject'), tone: confirm ? 'block' : 'allow', propagate: confirm })
      break
    }
    case 'campaign.new_domain':
      log({ kind: 'campaign', domain: str(event.domain), text: `${t('live.campaign')} ${str(event.campaign_id)}`, tone: 'warn', propagate: false })
      break
    case 'takedown.offline':
      log({ kind: 'takedown', domain: str(event.domain), text: t('live.offline'), tone: 'allow', propagate: false })
      break
    case 'watchlist.woke':
      log({ kind: 'watch', domain: str(event.domain), text: t('live.woke'), tone: 'warn', propagate: false })
      break
    case 'brand.spike':
      spike.value = { brand: str(event.brand_id), count: Number(event.count) }
      window.clearTimeout(spikeTimer)
      spikeTimer = window.setTimeout(() => { spike.value = null }, 9000)
      break
  }
}

function next() {
  current.value = queue.value[0] ?? null
  queue.value = queue.value.slice(1)
  if (!current.value) idleSince = Date.now()
}

// While nothing new arrives, replay recent block-band cases so the wall keeps telling the story.
function idleCheck() {
  now.value = Date.now()
  if (paused.value || current.value || Date.now() - idleSince < 12_000 || !replays.value.length) return
  const item = replays.value[replayIndex++ % replays.value.length]
  current.value = { key: `${item.domain}#${uid()}`, domain: item.domain, source: item.source, brand: item.brand, rev: 0, replay: true }
}

async function refreshTotals() {
  const value = await feed.totals()
  if (value) totals.value = value
}

function onKey(event: KeyboardEvent) {
  if (event.metaKey || event.ctrlKey || event.altKey) return
  if (event.key === ' ') paused.value = !paused.value
  else if (event.key === 'ArrowRight' || event.key === 'ArrowLeft' || event.key.toLowerCase() === 'n') next()
  else if (event.key.toLowerCase() === 'f') toggleFullscreen()
  else if (event.key === 'Escape' && !document.fullscreenElement) router.push({ name: 'queue' })
  else return
  event.preventDefault()
}

function toggleFullscreen() {
  if (document.fullscreenElement) document.exitFullscreen().catch(() => {})
  else document.documentElement.requestFullscreen?.().catch(() => {})
}

onMounted(async () => {
  window.addEventListener('keydown', onKey)
  stop = feed.subscribe(onLive)
  timers.push(window.setInterval(idleCheck, 1000))
  await refreshTotals()
  replays.value = await feed.replay()
  if (!feed.demo) {
    timers.push(window.setInterval(refreshTotals, 60_000))
    timers.push(window.setInterval(async () => { replays.value = await feed.replay() }, 120_000))
  }
})
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKey)
  timers.forEach((timer) => window.clearInterval(timer))
  window.clearTimeout(spikeTimer)
  stop?.()
})

const clock = computed(() => new Intl.DateTimeFormat(lang.value === 'ar' ? 'ar-AE' : 'en-GB', {
  timeZone: 'Asia/Dubai', hour: '2-digit', minute: '2-digit', second: '2-digit',
}).format(now.value))

function ago(at: number): string {
  const s = Math.max(0, Math.round((now.value - at) / 1000))
  return s < 60 ? `${s}s` : `${Math.round(s / 60)}m`
}
</script>

<template>
  <div class="live">
    <header class="bar">
      <RouterLink :to="{ name: 'queue' }" class="brand">
        <span class="mark" aria-hidden="true">KP</span>
        <span>KARTOSHKA<span class="dim">·POLICE</span></span>
      </RouterLink>
      <span class="onair" :class="{ off: !connected }"><i />{{ connected ? t('nav.live') : t('live.offline_socket') }}</span>
      <span v-if="feed.demo" class="demo">{{ t('live.demo') }}</span>
      <span v-if="paused" class="demo">{{ t('live.paused') }}</span>
      <span class="spacer" />
      <div class="kpis">
        <div><b>{{ shownCandidates.toLocaleString() }}</b><span>{{ t('live.candidates') }}</span></div>
        <div><b class="warn">{{ shownThreats.toLocaleString() }}</b><span>{{ t('live.threats') }}</span></div>
        <div><b class="block">{{ shownConfirmed.toLocaleString() }}</b><span>{{ t('live.confirmed') }}</span></div>
        <div><b>{{ shownBlocklist.toLocaleString() }}</b><span>{{ t('live.blocklist') }}</span></div>
      </div>
      <span class="clock mono">{{ clock }} <small>GST</small></span>
      <button class="ghost" @click="toggleLang">{{ lang === 'ar' ? 'EN' : 'ع' }}</button>
      <button class="ghost theme" :title="t(`theme.${theme}`)" :aria-label="t(`theme.${theme}`)" @click="cycleTheme">
        <svg viewBox="0 0 16 16" aria-hidden="true"><path :d="dark ? 'M8 5a3 3 0 1 1 0 6 3 3 0 0 1 0-6ZM8 1.5V3M8 13v1.5M1.5 8H3M13 8h1.5M3.4 3.4l1 1M11.6 11.6l1 1M3.4 12.6l1-1M11.6 4.4l1-1' : 'M13.5 9.5A5.5 5.5 0 0 1 6.5 2.5a5.5 5.5 0 1 0 7 7z'" /></svg>
      </button>
    </header>

    <Transition name="drop">
      <div v-if="spike" class="spike" role="alert">
        <b>{{ t('live.spike') }}</b> · {{ spike.count }} × {{ spike.brand }} · 1 h
      </div>
    </Transition>

    <div class="grid3">
      <aside class="col left">
        <h3>{{ t('live.radar') }}</h3>
        <Radar :blips="blips" />
        <ul class="ticker">
          <TransitionGroup name="row">
            <li v-for="c in candidates.slice(0, 14)" :key="c.id" :class="c.band">
              <span class="src">{{ c.source }}</span>
              <DefangedDomain :display="defang(c.domain)" />
              <span class="score">{{ c.score ?? '' }}</span>
              <span class="ago">{{ ago(c.at) }}</span>
            </li>
          </TransitionGroup>
        </ul>
      </aside>

      <main class="col center">
        <Transition name="swap" mode="out-in">
          <LiveStage v-if="current" :key="current.key" :item="current" :feed="feed" :paused="paused" @done="next" />
          <div v-else class="idle">
            <div class="idle-ring"><i /><i /><i /></div>
            <p>{{ t('live.waiting') }}</p>
          </div>
        </Transition>
        <div v-if="queue.length" class="upnext">
          <span class="muted small">{{ t('live.next') }}</span>
          <TransitionGroup name="row">
            <span v-for="item in queue" :key="item.key" class="q"><DefangedDomain :display="defang(item.domain)" /></span>
          </TransitionGroup>
        </div>
      </main>

      <aside class="col right">
        <h3>{{ t('live.response') }}</h3>
        <ul class="log">
          <TransitionGroup name="row">
            <li v-for="e in entries" :key="e.id" :class="e.tone">
              <div class="line"><DefangedDomain :display="defang(e.domain)" /><span class="ago">{{ ago(e.at) }}</span></div>
              <div class="what">{{ e.text }}</div>
              <Propagation v-if="e.propagate" dense />
            </li>
          </TransitionGroup>
        </ul>
      </aside>
    </div>

    <footer class="foot muted small">{{ t('live.keys') }}</footer>
  </div>
</template>

<style scoped>
/* The wall follows the console theme (system by default); in dark it reads as an operations centre. */
.live {
  min-height: 100vh; overflow-x: hidden; display: grid; grid-template-rows: auto auto 1fr auto; color: var(--text);
  background:
    radial-gradient(60% 50% at 50% -10%, color-mix(in srgb, var(--accent) 14%, transparent), transparent 70%),
    linear-gradient(color-mix(in srgb, var(--text) 2%, transparent) 1px, transparent 1px) 0 0 / 100% 32px,
    var(--bg);
}
.bar { display: flex; align-items: center; gap: 1rem; padding: 0.7rem 1.25rem; border-bottom: 1px solid var(--line); flex-wrap: wrap; background: color-mix(in srgb, var(--surface) 82%, transparent); backdrop-filter: blur(8px); position: sticky; top: 0; z-index: 5; }
.brand { display: inline-flex; align-items: center; gap: 0.5rem; color: var(--text); text-decoration: none; font-weight: 800; letter-spacing: 0.14em; font-size: 0.9rem; }
.brand .mark { display: inline-grid; place-items: center; width: 28px; height: 28px; border-radius: var(--radius-sm); background: var(--primary); color: var(--on-primary); font-size: 11px; letter-spacing: 0.04em; }
.dim { color: var(--muted); font-weight: 600; }
.onair { display: inline-flex; align-items: center; gap: 0.4rem; padding: 0.15rem 0.6rem; border-radius: 999px; font-size: 0.72rem; font-weight: 800; letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--block); border: 1px solid color-mix(in srgb, var(--block) 50%, transparent); background: var(--block-soft); }
.onair i { width: 0.5rem; height: 0.5rem; border-radius: 50%; background: var(--block); box-shadow: 0 0 8px var(--block); animation: kp-blink 1.2s infinite; }
.onair.off { color: var(--muted); border-color: var(--line); background: transparent; }
.onair.off i { background: var(--muted); box-shadow: none; animation: none; }
.demo { font-size: 0.7rem; font-weight: 800; letter-spacing: 0.12em; padding: 0.15rem 0.5rem; border-radius: 4px; background: var(--banner); color: var(--banner-text); border: 1px solid color-mix(in srgb, var(--banner-text) 40%, transparent); }
.spacer { flex: 1; }
.kpis { display: flex; gap: 1.4rem; }
.kpis div { display: grid; text-align: end; }
.kpis b { font-size: 1.35rem; font-variant-numeric: tabular-nums; line-height: 1.1; }
.kpis b.warn { color: var(--warn); }
.kpis b.block { color: var(--block); }
.kpis span { font-size: 0.66rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; }
.clock { font-size: 1.05rem; color: var(--muted); }
.clock small { font-size: 0.65rem; }
.bar button { color: var(--muted); }
.theme svg { width: 16px; height: 16px; fill: none; stroke: currentColor; stroke-width: 1.5; stroke-linecap: round; stroke-linejoin: round; }
@media (max-width: 900px) { .kpis { gap: 0.8rem; order: 5; width: 100%; justify-content: space-between; } .kpis div { text-align: start; } }

.spike { margin: 0.6rem 1.25rem 0; padding: 0.5rem 0.9rem; border-radius: 8px; background: var(--block-soft); color: var(--block); border: 1px solid var(--block); animation: kp-pulse 1.2s 3; }
.drop-enter-active, .drop-leave-active { transition: opacity 300ms, transform 300ms var(--ease-out); }
.drop-enter-from, .drop-leave-to { opacity: 0; transform: translateY(-8px); }

.grid3 { display: grid; grid-template-columns: 17rem minmax(0, 1fr) 19rem; gap: 1rem; padding: 1rem 1.25rem; min-height: 0; }
@media (max-width: 1280px) { .grid3 { grid-template-columns: 15rem minmax(0, 1fr); } .right { grid-column: 1 / -1; } }
@media (max-width: 860px) { .grid3 { grid-template-columns: minmax(0, 1fr); } .center { order: -1; } }
.col h3 { font-size: 0.7rem; letter-spacing: 0.16em; color: var(--muted); margin: 0 0 0.6rem; }
.left, .right { min-width: 0; }

.ticker, .log { list-style: none; margin: 0.8rem 0 0; padding: 0; display: grid; gap: 0.3rem; }
.ticker li { display: grid; grid-template-columns: 2.6rem minmax(0, 1fr) auto auto; gap: 0.4rem; align-items: center; padding: 0.3rem 0.45rem; border-radius: 6px;
  background: var(--surface); border: 1px solid var(--line); font-size: 0.76rem; transition: border-color 400ms, box-shadow 400ms; }
.ticker li .domain { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 0.74rem; }
.ticker .src { font-family: var(--mono); font-size: 0.62rem; text-transform: uppercase; color: var(--accent); }
.ticker .score { font-family: var(--mono); font-weight: 700; }
.ticker li.warn { border-color: color-mix(in srgb, var(--warn) 50%, var(--line)); }
.ticker li.warn .score { color: var(--warn); }
.ticker li.block { border-color: var(--block); box-shadow: 0 0 14px -6px var(--block); }
.ticker li.block .score { color: var(--block); }
.ago { font-size: 0.66rem; color: var(--muted); font-variant-numeric: tabular-nums; }

.center { min-width: 0; display: grid; gap: 0.75rem; align-content: start; }
.swap-enter-active { transition: opacity 380ms var(--ease-out), transform 380ms var(--ease-out); }
.swap-leave-active { transition: opacity 220ms ease, transform 220ms ease; }
.swap-enter-from { opacity: 0; transform: translateY(14px) scale(0.985); }
.swap-leave-to { opacity: 0; transform: translateY(-10px) scale(0.985); }
.idle { min-height: 26rem; display: grid; place-content: center; justify-items: center; gap: 1rem; border: 1px dashed var(--line); border-radius: 14px; color: var(--muted); }
.idle-ring { position: relative; width: 5rem; height: 5rem; }
.idle-ring i { position: absolute; inset: 0; border-radius: 50%; border: 2px solid var(--accent); opacity: 0; animation: idle 2.4s ease-out infinite; }
.idle-ring i:nth-child(2) { animation-delay: 0.8s; }
.idle-ring i:nth-child(3) { animation-delay: 1.6s; }
@keyframes idle { from { transform: scale(0.2); opacity: 0.9; } to { transform: scale(1.3); opacity: 0; } }
.upnext { display: flex; gap: 0.4rem; align-items: center; flex-wrap: wrap; }
.q { padding: 0.15rem 0.5rem; border-radius: 6px; border: 1px solid var(--line); background: var(--surface); font-size: 0.74rem; }

.log li { padding: 0.5rem 0.6rem; border-radius: 8px; background: var(--surface); border: 1px solid var(--line); border-inline-start: 3px solid var(--muted); display: grid; gap: 0.3rem; }
.log li.block { border-inline-start-color: var(--block); }
.log li.allow { border-inline-start-color: var(--allow); }
.log li.warn { border-inline-start-color: var(--warn); }
.log .line { display: flex; justify-content: space-between; gap: 0.5rem; font-size: 0.78rem; }
.log .line .domain { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.log .what { font-size: 0.78rem; color: var(--muted); }
.log li.block .what { color: var(--block); font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; }

.foot { padding: 0.5rem 1.25rem 0.8rem; text-align: center; }
</style>
