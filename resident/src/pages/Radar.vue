<script setup lang="ts">
// Scam radar: what is active now in the UAE, built like My reports. A summary row, a chart by kind of scam
// (tap a row to filter), and one card per imitated brand with a confirmed/suspected bar, today's trend and,
// when opened, the defanged fake sites, the advice and the real service. Refreshes every minute and marks
// brands that grew since this device last looked. Domains are defanged and never links, so the radar never
// advertises a live scam.
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { radar, type Radar, type RadarBrand } from '../api'
import { lang, tr } from '../i18n'

const data = ref<Radar | null>(null)
const error = ref('')
const loading = ref(false)
const loadedAt = ref<number | null>(null)
const now = ref(Date.now())
const filter = ref<string>('all')
const open = ref<Set<string>>(new Set())
const grown = ref<Record<string, number>>({})
let timers: number[] = []

// Last seen active count per brand, so a brand that grew since the last visit gets a "+N" badge.
const SEEN_KEY = 'kp.radar.seen'
function readSeen(): Record<string, number> {
  try {
    return JSON.parse(localStorage.getItem(SEEN_KEY) ?? '{}') as Record<string, number>
  } catch {
    return {}
  }
}

async function load() {
  if (loading.value) return
  loading.value = true
  try {
    const next = await radar()
    const seen = readSeen()
    const marks = { ...grown.value }
    for (const b of next.brands) {
      const before = seen[b.brand_id]
      if (before !== undefined && b.active > before) marks[b.brand_id] = (marks[b.brand_id] ?? 0) + b.active - before
      seen[b.brand_id] = b.active
    }
    try {
      localStorage.setItem(SEEN_KEY, JSON.stringify(seen))
    } catch {
      /* ignore */
    }
    grown.value = marks
    data.value = next
    error.value = ''
    if (filter.value !== 'all' && !next.brands.some((b) => category(b) === filter.value)) filter.value = 'all'
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loadedAt.value = Date.now()
    loading.value = false
  }
}

function onVisible() {
  if (document.visibilityState === 'visible') load()
}
onMounted(() => {
  load()
  timers.push(window.setInterval(() => { if (document.visibilityState === 'visible') load() }, 60_000))
  timers.push(window.setInterval(() => { now.value = Date.now() }, 5_000))
  document.addEventListener('visibilitychange', onVisible)
})
onUnmounted(() => {
  timers.forEach((t) => window.clearInterval(t))
  timers = []
  document.removeEventListener('visibilitychange', onVisible)
})

// --- categories -------------------------------------------------------------------------------------

const CATEGORY: Record<string, { en: string; ar: string; icon: string }> = {
  police: { en: 'Police & fines', ar: 'الشرطة والمخالفات', icon: 'M12 2.5 4 5.5v6c0 4.7 3.4 9 8 10 4.6-1 8-5.3 8-10v-6l-8-3zM12 8v5M12 16h.01' },
  government: { en: 'Government', ar: 'خدمات حكومية', icon: 'M3 9.5 12 4l9 5.5M5 10v8M9.5 10v8M14.5 10v8M19 10v8M3 20.5h18' },
  identity: { en: 'ID & sign-in', ar: 'الهوية والدخول', icon: 'M4 5h16a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1zM9 9.5a2 2 0 1 1 0 4 2 2 0 0 1 0-4zM6 16.5c.6-1.3 1.7-2 3-2s2.4.7 3 2M14.5 10h3.5M14.5 13.5h3.5' },
  delivery: { en: 'Parcels', ar: 'الطرود', icon: 'M12 3 3.5 7.5v9L12 21l8.5-4.5v-9L12 3zM3.5 7.5 12 12l8.5-4.5M12 12v9M7.8 5.3l8.5 4.5' },
  bank: { en: 'Banks', ar: 'البنوك', icon: 'M3 7h18v11a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V7zM3 7l2-3h14l2 3M3 11h18M7 15h4' },
  telecom: { en: 'Telecom', ar: 'الاتصالات', icon: 'M7 3h10a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1zM11 18h2' },
  utility: { en: 'Bills', ar: 'الفواتير', icon: 'M13 2 5 13h6l-1 9 8-11h-6l1-9z' },
  other: { en: 'Other', ar: 'أخرى', icon: 'M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18zM12 8v5M12 16h.01' },
}
const category = (b: RadarBrand) => (b.category && CATEGORY[b.category] ? b.category : 'other')
const catLabel = (key: string) => tr(CATEGORY[key]?.en ?? key, CATEGORY[key]?.ar ?? key)

/** One row per kind of scam, biggest first; the chart and the filter chips both use it. */
const groups = computed(() => {
  const out = new Map<string, { key: string; active: number; newToday: number; brands: RadarBrand[] }>()
  for (const b of data.value?.brands ?? []) {
    const key = category(b)
    const g = out.get(key) ?? { key, active: 0, newToday: 0, brands: [] }
    g.active += b.active
    g.newToday += b.new_today
    g.brands.push(b)
    out.set(key, g)
  }
  return [...out.values()].sort((a, b) => b.active - a.active)
})
const maxGroup = computed(() => Math.max(1, ...groups.value.map((g) => g.active)))
function imitating(brands: RadarBrand[]): string {
  const names = brands.slice(0, 3).map((b) => (lang.value === 'ar' ? b.brand_ar : b.brand)).join(lang.value === 'ar' ? '، ' : ', ')
  return tr(`Imitating ${names}`, `تقلّد ${names}`)
}

const visible = computed(() => (data.value?.brands ?? []).filter((b) => filter.value === 'all' || category(b) === filter.value))
const maxBrand = computed(() => Math.max(1, ...(data.value?.brands ?? []).map((b) => b.active)))

function pick(key: string) {
  filter.value = filter.value === key ? 'all' : key
}

// --- per brand --------------------------------------------------------------------------------------

type Trend = 'up' | 'down' | 'flat'
function trend(today: number, yesterday: number): Trend {
  return today > yesterday ? 'up' : today < yesterday ? 'down' : 'flat'
}
function delta(today: number, yesterday: number): string {
  const d = today - yesterday
  return d > 0 ? `+${d}` : `${d}`
}
function trendText(today: number, yesterday: number): string {
  const d = today - yesterday
  if (d === 0) return tr('Same as yesterday', 'مثل أمس')
  return d > 0 ? tr(`+${d} vs yesterday`, `+${d} مقارنة بأمس`) : tr(`${d} vs yesterday`, `${d} مقارنة بأمس`)
}
/** Rising today: red; active but calm: amber; nothing new: grey. */
function tone(b: RadarBrand): 'hot' | 'warm' | 'calm' {
  if (b.new_today > b.yesterday && b.new_today > 0) return 'hot'
  return b.new_today > 0 ? 'warm' : 'calm'
}
/** Latin initials in both languages, like the brands' own marks (Arabic initials do not read as a monogram). */
function initials(b: RadarBrand): string {
  const name = b.brand
  const words = name.replace(/[()&]/g, ' ').split(/\s+/).filter(Boolean)
  return (words.length > 1 ? words[0][0] + words[1][0] : name.slice(0, 2)).toUpperCase()
}
function toggle(b: RadarBrand) {
  const next = new Set(open.value)
  if (next.has(b.brand_id)) next.delete(b.brand_id)
  else next.add(b.brand_id)
  open.value = next
  if (grown.value[b.brand_id]) {
    const { [b.brand_id]: _, ...rest } = grown.value
    grown.value = rest
  }
}

function ago(value: number | null): string {
  if (value === null) return ''
  const seconds = Math.min(0, Math.round((value - Math.max(now.value, Date.now())) / 1000))
  const rtf = new Intl.RelativeTimeFormat(lang.value === 'ar' ? 'ar-AE' : 'en-AE', { numeric: 'auto' })
  const abs = Math.abs(seconds)
  if (abs < 60) return rtf.format(seconds, 'second')
  if (abs < 3600) return rtf.format(Math.round(seconds / 60), 'minute')
  return rtf.format(Math.round(seconds / 3600), 'hour')
}

const totals = computed(() => data.value?.totals)
const days = computed(() => data.value?.window_days ?? 7)
</script>

<template>
  <main class="radar">
    <div class="row-head">
      <div>
        <h1>{{ tr('Scam radar', 'رادار الاحتيال') }}</h1>
        <p class="small muted live">
          <span class="dot" :class="{ busy: loading }" />
          <template v-if="loading">{{ tr('Updating…', 'جارٍ التحديث…') }}</template>
          <template v-else-if="loadedAt">{{ tr(`Last ${days} days · updated`, `آخر ${days} أيام · تحديث`) }} {{ ago(loadedAt) }}</template>
        </p>
      </div>
      <button class="refresh" :disabled="loading" :aria-label="tr('Refresh', 'تحديث')" @click="load">
        <svg viewBox="0 0 24 24" :class="{ spin: loading }" aria-hidden="true"><path d="M20 12a8 8 0 1 1-2.3-5.7M20 4v5h-5" /></svg>
      </button>
    </div>

    <p v-if="error" class="error">{{ error }}</p>

    <!-- First load -->
    <template v-if="!data && loading">
      <div class="summary"><span v-for="i in 4" :key="i" class="skeleton tile" /></div>
      <div class="card"><span v-for="i in 3" :key="i" class="skeleton line" /></div>
      <div v-for="i in 2" :key="i" class="card"><span class="skeleton line" /><span class="skeleton line short" /></div>
    </template>

    <template v-else-if="data && totals">
      <section class="summary rise">
        <div class="hot"><b>{{ totals.active }}</b><span>{{ tr('Active scam sites', 'مواقع احتيال نشطة') }}</span></div>
        <div class="warm">
          <b>{{ totals.new_today }}<i :class="['trend', trend(totals.new_today, totals.yesterday)]" aria-hidden="true" /></b>
          <span>{{ tr('New today', 'جديد اليوم') }} · {{ trendText(totals.new_today, totals.yesterday) }}</span>
        </div>
        <div><b>{{ totals.confirmed }}</b><span>{{ tr('Confirmed by police', 'أكدتها الشرطة') }}</span></div>
        <div class="soft"><b>{{ totals.suspected }}</b><span>{{ tr('Suspected, under review', 'مشتبه بها، قيد المراجعة') }}</span></div>
      </section>

      <section v-if="!totals.active" class="card empty rise">
        <svg viewBox="0 0 64 64" aria-hidden="true"><path d="M32 6 12 13v15c0 12 8.5 22.5 20 26 11.5-3.5 20-14 20-26V13L32 6z" /><path d="m23 31 6 6 12-12" /></svg>
        <h2>{{ tr('No active scam sites right now', 'لا توجد مواقع احتيال نشطة الآن') }}</h2>
        <p class="muted">{{ tr('When police confirm a fake site, or many residents meet one, it shows up here.', 'عندما تؤكد الشرطة موقعًا مزيفًا، أو يصادفه كثير من السكان، يظهر هنا.') }}</p>
      </section>

      <template v-else>
        <!-- What is going on, by kind of scam: also the filter -->
        <section class="card kinds rise">
          <h2>{{ tr('What scammers imitate now', 'ما يقلّده المحتالون الآن') }}</h2>
          <button v-for="(g, i) in groups" :key="g.key" type="button" class="kind" :aria-pressed="filter === g.key" @click="pick(g.key)">
            <span class="kicon"><svg viewBox="0 0 24 24" aria-hidden="true"><path :d="CATEGORY[g.key].icon" /></svg></span>
            <span class="kbody">
              <span class="kline"><strong>{{ catLabel(g.key) }}</strong>
                <span class="small nums"><b>{{ g.active }}</b><bdi v-if="g.newToday" class="plus">{{ tr(`+${g.newToday} today`, `+${g.newToday} اليوم`) }}</bdi></span></span>
              <span class="kbar"><i :style="{ transform: `scaleX(${g.active / maxGroup})`, animationDelay: `${i * 70}ms` }" /></span>
              <span class="small muted">{{ imitating(g.brands) }}</span>
            </span>
          </button>
        </section>

        <div class="chips" role="group" :aria-label="tr('Filter', 'تصفية')">
          <button type="button" class="chip" :aria-pressed="filter === 'all'" @click="filter = 'all'">
            {{ tr('All', 'الكل') }}<span class="n">{{ data.brands.length }}</span>
          </button>
          <button v-for="g in groups" :key="g.key" type="button" class="chip" :aria-pressed="filter === g.key" @click="filter = g.key">
            {{ catLabel(g.key) }}<span class="n">{{ g.brands.length }}</span>
          </button>
        </div>

        <TransitionGroup name="list" tag="div" class="list">
          <article v-for="(b, i) in visible" :key="b.brand_id" class="card brand" :class="[tone(b), { grew: grown[b.brand_id] }]"
                   :style="{ animationDelay: `${i * 50}ms` }">
            <button class="head" :aria-expanded="open.has(b.brand_id)" @click="toggle(b)">
              <span class="avatar" aria-hidden="true">{{ initials(b) }}</span>
              <span class="title">
                <strong>{{ lang === 'ar' ? b.brand_ar : b.brand }}</strong>
                <span class="small muted">{{ catLabel(category(b)) }} · {{ tr(`${b.active} active`, `${b.active} نشط`) }}<template v-if="b.new_today"> · <bdi class="today">{{ tr(`+${b.new_today} today`, `+${b.new_today} اليوم`) }}</bdi></template></span>
              </span>
              <span v-if="grown[b.brand_id]" class="badge new">+{{ grown[b.brand_id] }} {{ tr('new', 'جديد') }}</span>
              <span v-else class="pill" :class="trend(b.new_today, b.yesterday)" :title="trendText(b.new_today, b.yesterday)"
                    :aria-label="trendText(b.new_today, b.yesterday)">
                <i :class="['trend', trend(b.new_today, b.yesterday)]" aria-hidden="true" />{{ b.new_today === b.yesterday ? '' : delta(b.new_today, b.yesterday) }}
              </span>
              <svg class="chev" :class="{ open: open.has(b.brand_id) }" viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 6 6-6 6" /></svg>
            </button>

            <div class="stack-bar" :style="{ '--w': b.active / maxBrand }" role="img"
                 :aria-label="tr(`${b.confirmed} confirmed, ${b.suspected} suspected`, `${b.confirmed} مؤكد، ${b.suspected} مشتبه به`)">
              <i class="c" :style="{ flexGrow: b.confirmed }" /><i class="s" :style="{ flexGrow: b.suspected }" />
            </div>
            <p class="legend small">
              <span><i class="c" />{{ tr(`${b.confirmed} confirmed by police`, `${b.confirmed} أكدتها الشرطة`) }}</span>
              <span><i class="s" />{{ tr(`${b.suspected} suspected`, `${b.suspected} مشتبه بها`) }}</span>
            </p>

            <p v-if="b.tip_en" class="tip">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9c.6.4 1 1.1 1 1.8V16h5v-.3c0-.7.4-1.4 1-1.8A6 6 0 0 0 12 3z" /></svg>
              <span>{{ lang === 'ar' ? b.tip_ar : b.tip_en }}</span>
            </p>

            <div v-if="open.has(b.brand_id)" class="details rise">
              <div class="days">
                <div><b>{{ b.new_today }}</b><span>{{ tr('New today', 'جديد اليوم') }}</span></div>
                <div><b>{{ b.yesterday }}</b><span>{{ tr('Yesterday', 'أمس') }}</span></div>
                <div :class="trend(b.new_today, b.yesterday)"><b><i :class="['trend', trend(b.new_today, b.yesterday)]" aria-hidden="true" /></b>
                  <span>{{ trendText(b.new_today, b.yesterday) }}</span></div>
              </div>
              <template v-if="b.examples.length">
                <p class="small muted label">{{ tr('Fake sites confirmed by police (do not open):', 'مواقع مزيفة أكدتها الشرطة (لا تفتحها):') }}</p>
                <ul class="fakes">
                  <li v-for="d in b.examples" :key="d" class="domain">{{ d }}</li>
                </ul>
              </template>
              <a v-if="b.safe_action" class="button safe" :href="b.safe_action.url" rel="noopener">
                {{ lang === 'ar' ? b.safe_action.label_ar : b.safe_action.label_en }}
              </a>
              <RouterLink :to="{ name: 'check' }" class="button ghost">{{ tr('Got a link like this? Check it', 'وصلك رابط مشابه؟ افحصه') }}</RouterLink>
            </div>
          </article>
        </TransitionGroup>
      </template>
    </template>
  </main>
</template>

<style scoped>
.row-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; }
.live { display: flex; align-items: center; gap: 0.4rem; margin-top: -0.4rem; }
.dot { width: 0.5rem; height: 0.5rem; border-radius: 50%; background: var(--allow); }
.dot.busy { background: var(--accent); animation: kp-pulse 1s infinite; }
.refresh { min-height: 2.6rem; width: 2.6rem; padding: 0; border-radius: 999px; }
.refresh svg, .chev, .tip svg, .kicon svg { width: 1.2rem; height: 1.2rem; fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
.spin { animation: kp-spin 0.9s linear infinite; }

.summary { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0.5rem; margin: 0.5rem 0 0.75rem; }
.summary div { display: grid; gap: 0.1rem; padding: 0.6rem 0.7rem; background: var(--surface); border: 1px solid var(--line); border-radius: 12px; }
.summary b { display: flex; align-items: center; gap: 0.3rem; font-size: 1.35rem; font-variant-numeric: tabular-nums; line-height: 1.1; }
.summary span { font-size: 0.72rem; color: var(--muted); line-height: 1.2; }
.summary .hot b { color: var(--block); }
.summary .warm b { color: var(--warn); }
.summary .soft b { color: var(--muted); }
.summary .tile { height: 4rem; border-radius: 12px; }
@media (max-width: 420px) { .summary { grid-template-columns: repeat(2, minmax(0, 1fr)); } }

/* Trend arrow: a small CSS triangle, so it needs no icon font. */
.trend { display: inline-block; width: 0; height: 0; border-inline: 0.32rem solid transparent; }
.trend.up { border-bottom: 0.45rem solid var(--block); }
.trend.down { border-top: 0.45rem solid var(--allow); }
.trend.flat { width: 0.6rem; height: 2px; border: 0; background: var(--muted); }

.kinds h2 { margin: 0 0 0.6rem; font-size: 1rem; }
.kind { display: flex; width: 100%; gap: 0.7rem; align-items: flex-start; padding: 0.55rem 0.5rem; margin: 0 -0.5rem; width: calc(100% + 1rem);
  min-height: 0; background: none; border: 1px solid transparent; border-radius: 12px; text-align: start; font-weight: 400; }
.kind[aria-pressed='true'] { background: var(--grey-soft); border-color: var(--line); }
.kicon { flex: none; display: grid; place-items: center; width: 2.2rem; height: 2.2rem; border-radius: 10px; background: var(--block-soft); color: var(--block); }
.kbody { display: grid; gap: 0.3rem; flex: 1; min-width: 0; }
.kline { display: flex; justify-content: space-between; align-items: baseline; gap: 0.5rem; }
.kline b { font-size: 1rem; font-variant-numeric: tabular-nums; }
.nums { display: inline-flex; align-items: baseline; gap: 0.45rem; flex: none; }
.plus { color: var(--warn); font-weight: 600; }
.kbar { height: 6px; border-radius: 6px; background: var(--grey-soft); overflow: hidden; }
.kbar i { display: block; height: 100%; border-radius: 6px; background: linear-gradient(90deg, var(--warn), var(--block)); transform-origin: left;
  transition: transform 700ms cubic-bezier(0.22, 1, 0.36, 1); animation: bar-in 900ms cubic-bezier(0.22, 1, 0.36, 1) both; }
[dir='rtl'] .kbar i { transform-origin: right; background: linear-gradient(270deg, var(--warn), var(--block)); }
@keyframes bar-in { from { transform: scaleX(0); } }

.chips { margin-bottom: 0.85rem; }
.list { display: grid; }
.list-enter-active, .list-leave-active { transition: opacity 240ms ease, transform 240ms cubic-bezier(0.22, 1, 0.36, 1); }
.list-enter-from { opacity: 0; transform: translateY(8px); }
.list-leave-to { opacity: 0; transform: scale(0.97); }
.list-leave-active { position: absolute; }
.list-move { transition: transform 260ms cubic-bezier(0.22, 1, 0.36, 1); }

.brand { --tone: var(--warn); position: relative; overflow: hidden; animation: kp-rise 360ms cubic-bezier(0.22, 1, 0.36, 1) both; }
.brand::before { content: ''; position: absolute; inset-block: 0; inset-inline-start: 0; width: 4px; background: var(--tone); }
.brand.hot { --tone: var(--block); }
.brand.calm { --tone: var(--dot); }
.brand.grew { border-color: var(--tone); animation: kp-rise 360ms both, grew 1.4s 400ms 2; }
@keyframes grew { 0% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--tone) 55%, transparent); } 100% { box-shadow: 0 0 0 10px transparent; } }

.head { display: flex; width: 100%; align-items: center; gap: 0.75rem; padding: 0; min-height: 0; text-align: start; background: none; border: 0; font-weight: 400; }
.avatar { flex: none; display: grid; place-items: center; width: 2.7rem; height: 2.7rem; border-radius: 50%; font-weight: 800; font-size: 0.9rem;
  color: var(--tone); background: color-mix(in srgb, var(--tone) 14%, var(--surface)); border: 2px solid color-mix(in srgb, var(--tone) 45%, transparent); }
.title { display: grid; gap: 0.1rem; flex: 1; min-width: 0; }
.title strong { font-size: 1.05rem; }
.today { color: var(--warn); font-weight: 600; }
.pill { display: inline-flex; align-items: center; gap: 0.3rem; padding: 0.15rem 0.55rem; border-radius: 999px; font-size: 0.8rem; font-weight: 700;
  font-variant-numeric: tabular-nums; background: var(--grey-soft); color: var(--muted); }
.pill.up { background: var(--block-soft); color: var(--block); }
.pill.down { background: var(--allow-soft); color: var(--allow); }
.badge.new { background: var(--tone); color: var(--on-accent); animation: kp-rise 300ms both; }
.chev { color: var(--muted); transition: transform 220ms ease; flex: none; }
[dir='rtl'] .chev { transform: scaleX(-1); }
.chev.open { transform: rotate(90deg); }

.stack-bar { display: flex; gap: 2px; height: 8px; margin: 0.9rem 0 0.35rem; width: calc(max(var(--w), 0.08) * 100%); border-radius: 8px; overflow: hidden;
  transform-origin: left; animation: bar-in 900ms cubic-bezier(0.22, 1, 0.36, 1) both; }
[dir='rtl'] .stack-bar { transform-origin: right; }
.stack-bar i { display: block; min-width: 0; flex-basis: 0; }
.c { background: var(--block); }
.s { background: var(--warn); }
.legend { display: flex; flex-wrap: wrap; gap: 0.25rem 0.9rem; margin: 0; color: var(--muted); }
.legend span { display: inline-flex; align-items: center; gap: 0.35rem; }
.legend i { width: 0.6rem; height: 0.6rem; border-radius: 2px; }
.tip { display: flex; gap: 0.5rem; align-items: flex-start; margin: 0.7rem 0 0; padding: 0.55rem 0.7rem; border-radius: 10px; background: var(--grey-soft); font-size: 0.9rem; }
.tip svg { flex: none; color: var(--warn); margin-top: 0.1rem; }

.details { display: grid; gap: 0.6rem; margin-top: 0.8rem; padding-top: 0.8rem; border-top: 1px solid var(--line); }
.days { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0.4rem; }
.days div { display: grid; gap: 0.1rem; padding: 0.5rem 0.6rem; border-radius: 10px; background: var(--grey-soft); }
.days b { display: flex; align-items: center; min-height: 1.4rem; font-size: 1.15rem; font-variant-numeric: tabular-nums; }
.days span { font-size: 0.72rem; color: var(--muted); line-height: 1.2; }
.days .up span { color: var(--block); }
.days .down span { color: var(--allow); }
.label { margin: 0; }
.fakes { list-style: none; padding: 0; margin: 0; display: flex; flex-wrap: wrap; gap: 0.35rem; }
.fakes li { padding: 0.2rem 0.6rem; border-radius: 8px; background: var(--block-soft); color: var(--block); font-size: 0.85rem; direction: ltr; unicode-bidi: isolate; }
.button.ghost { width: 100%; background: transparent; color: var(--text); border: 1px solid var(--line); }

.empty { display: grid; justify-items: center; text-align: center; gap: 0.4rem; padding: 2rem 1.2rem; }
.empty svg { width: 4rem; height: 4rem; fill: none; stroke: var(--allow); stroke-width: 2.5; stroke-linecap: round; stroke-linejoin: round; margin-bottom: 0.4rem; }
.line { display: block; height: 0.8rem; margin: 0.5rem 0; }
.line.short { width: 60%; }
</style>
