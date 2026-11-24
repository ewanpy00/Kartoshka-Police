<script setup lang="ts">
// My reports: every report this device sent, as a tracker. Each card shows where the report is now (ring and
// stage bar), what happens next, how many other residents it protected, and the full dated timeline.
// The stages come from GET /v1/reports/{id} (core/app/reports.py timeline); stages not reached yet are drawn
// as placeholders. Only this device knows the report ids and tokens.
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { reportStatus, type ReportStatus, type Step } from '../api'
import { lang, tr } from '../i18n'
import { defang, forgetReport, hostOf, savedReports, type SavedReport } from '../store'

interface Row { saved: SavedReport; status: ReportStatus | null; missing: boolean; changed: boolean; open: boolean }
type Filter = 'all' | 'active' | 'confirmed' | 'closed'
type Tone = 'info' | 'review' | 'good' | 'neutral'

const rows = ref<Row[]>([])
const loading = ref(false)
const loadedAt = ref<number | null>(null)
const now = ref(Date.now())
const filter = ref<Filter>('all')
const armed = ref<string | null>(null)
const copied = ref<string | null>(null)
let timers: number[] = []

const SEEN_KEY = 'kp.reports.seen'
function readSeen(): Record<string, string> {
  try {
    return JSON.parse(localStorage.getItem(SEEN_KEY) ?? '{}') as Record<string, string>
  } catch {
    return {}
  }
}
function writeSeen(seen: Record<string, string>) {
  try {
    localStorage.setItem(SEEN_KEY, JSON.stringify(seen))
  } catch {
    /* ignore */
  }
}

async function load() {
  if (loading.value) return
  loading.value = true
  const saved = savedReports()
  const previous = new Map(rows.value.map((row) => [row.saved.id, row]))
  const next: Row[] = saved.map((s) => previous.get(s.id) ?? { saved: s, status: null, missing: false, changed: false, open: false })
  rows.value = next
  const seen = readSeen()
  // Mutate through rows.value: its items are the reactive proxies, `next` holds the raw objects.
  await Promise.all(rows.value.map(async (row) => {
    try {
      const status = await reportStatus(row.saved.id, row.saved.token)
      const before = seen[row.saved.id]
      if (before && before !== status.status) row.changed = true
      seen[row.saved.id] = status.status
      row.status = status
      row.missing = false
    } catch {
      if (!row.status) row.missing = true
    }
  }))
  writeSeen(seen)
  loadedAt.value = Date.now()
  loading.value = false
}

function onVisible() {
  if (document.visibilityState === 'visible') load()
}

onMounted(() => {
  load()
  timers.push(window.setInterval(() => { if (document.visibilityState === 'visible') load() }, 30_000))
  timers.push(window.setInterval(() => { now.value = Date.now() }, 5_000))
  document.addEventListener('visibilitychange', onVisible)
})
onUnmounted(() => {
  timers.forEach((timer) => window.clearInterval(timer))
  timers = []
  document.removeEventListener('visibilitychange', onVisible)
})

// --- status model -----------------------------------------------------------------------------------

const META: Record<string, { tone: Tone; en: string; ar: string; nextEn: string; nextAr: string }> = {
  sent: { tone: 'info', en: 'We received your report', ar: 'استلمنا بلاغك',
    nextEn: 'Our engine is opening the link in a sandbox.', nextAr: 'يفتح نظامنا الرابط الآن في بيئة معزولة.' },
  analysed: { tone: 'info', en: 'The link has been checked', ar: 'تم فحص الرابط',
    nextEn: 'If it looks risky, a police officer reviews it next.', nextAr: 'إذا بدا خطرًا، يراجعه ضابط شرطة بعد ذلك.' },
  in_review: { tone: 'review', en: 'A police officer is reviewing it', ar: 'يراجعه ضابط شرطة الآن',
    nextEn: 'You will see the decision here. Nothing else is needed from you.', nextAr: 'سترى القرار هنا. لا تحتاج إلى فعل أي شيء آخر.' },
  confirmed: { tone: 'good', en: 'Confirmed as a scam and blocked', ar: 'تم تأكيده كاحتيال وحظره',
    nextEn: 'Phones with Kartoshka now stop this site. We have asked for it to be taken down.', nextAr: 'الهواتف التي تستخدم كارتوشكا توقف هذا الموقع الآن، وطلبنا إيقافه.' },
  taken_down: { tone: 'good', en: 'The site has been taken down', ar: 'تم إيقاف الموقع',
    nextEn: 'Case closed. Thank you for reporting it.', nextAr: 'أُغلقت القضية. شكرًا لإبلاغك.' },
  rejected: { tone: 'neutral', en: 'Reviewed: not confirmed as a scam', ar: 'تمت المراجعة: لم يتأكد أنه احتيال',
    nextEn: 'Still unsure? Do not enter codes or card details on it.', nextAr: 'ما زلت غير متأكد؟ لا تُدخل رموزًا أو بيانات بطاقة فيه.' },
}
const ICON: Record<string, string> = {
  sent: 'M3 11.5 21 3l-7.5 18-2.5-7.5L3 11.5zM11 13.5 21 3',
  analysed: 'M10.5 4a6.5 6.5 0 1 1 0 13 6.5 6.5 0 0 1 0-13zM15.5 15.5 21 21',
  in_review: 'M2.5 12S6 5 12 5s9.5 7 9.5 7-3.5 7-9.5 7-9.5-7-9.5-7zM12 9a3 3 0 1 1 0 6 3 3 0 0 1 0-6z',
  confirmed: 'M12 2.5 4 5.5v6c0 4.7 3.4 9 8 10 4.6-1 8-5.3 8-10v-6l-8-3zM8.5 12l2.5 2.5 4.5-5',
  taken_down: 'M12 2.5 4 5.5v6c0 4.7 3.4 9 8 10 4.6-1 8-5.3 8-10v-6l-8-3zM8.5 12l2.5 2.5 4.5-5',
  rejected: 'M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18zM8 12h8',
}

function meta(row: Row) {
  return META[row.status?.status ?? 'sent'] ?? META.sent
}

/** The stage bar: the API's steps without "impact", plus placeholders for stages not reached yet. */
function stages(status: ReportStatus): Step[] {
  const list = status.steps.filter((s) => s.id !== 'impact')
  const decided = list.some((s) => s.id === 'confirmed' || s.id === 'rejected')
  if (!decided) {
    list.push({ id: 'decision', done: false, at: null, en: 'Police decision', ar: 'قرار الشرطة' })
    list.push({ id: 'taken_down', done: false, at: null, en: 'Site taken down', ar: 'إيقاف الموقع' })
  }
  return list
}
function progress(status: ReportStatus): number {
  const list = stages(status)
  return list.filter((s) => s.done).length / list.length
}
function current(status: ReportStatus): number {
  const list = stages(status)
  const index = list.findIndex((s) => !s.done)
  return index < 0 ? list.length - 1 : index
}
const SHORT: Record<string, [string, string]> = {
  sent: ['Sent', 'أُرسل'], analysed: ['Checked', 'فُحص'], in_review: ['Review', 'مراجعة'], decision: ['Decision', 'القرار'],
  confirmed: ['Confirmed', 'مؤكد'], rejected: ['Not confirmed', 'غير مؤكد'], taken_down: ['Taken down', 'أُوقف'],
}
function short(step: Step): string {
  const pair = SHORT[step.id]
  return pair ? tr(pair[0], pair[1]) : (lang.value === 'ar' ? step.ar : step.en)
}

// --- list, filters and summary ----------------------------------------------------------------------

function group(row: Row): Filter {
  const s = row.status?.status
  if (s === 'confirmed' || s === 'taken_down') return 'confirmed'
  if (s === 'rejected') return 'closed'
  return 'active'
}
const counts = computed(() => {
  const c = { all: rows.value.length, active: 0, confirmed: 0, closed: 0 }
  rows.value.forEach((row) => { c[group(row)] += 1 })
  return c
})
const protectedCount = computed(() => rows.value.reduce((total, row) => total + (row.status?.blocked_count ?? 0), 0))
const visible = computed(() => rows.value.filter((row) => filter.value === 'all' || group(row) === filter.value))
const FILTERS: [Filter, string, string][] = [
  ['all', 'All', 'الكل'], ['active', 'In progress', 'قيد المتابعة'], ['confirmed', 'Confirmed', 'مؤكدة'], ['closed', 'Not confirmed', 'غير مؤكدة'],
]

function ago(value: string | number | null): string {
  if (value === null) return ''
  const seconds = Math.min(0, Math.round(((typeof value === 'number' ? value : Date.parse(value)) - Math.max(now.value, Date.now())) / 1000))
  const rtf = new Intl.RelativeTimeFormat(lang.value === 'ar' ? 'ar-AE' : 'en-AE', { numeric: 'auto' })
  const abs = Math.abs(seconds)
  if (abs < 60) return rtf.format(Math.round(seconds), 'second')
  if (abs < 3600) return rtf.format(Math.round(seconds / 60), 'minute')
  if (abs < 86400) return rtf.format(Math.round(seconds / 3600), 'hour')
  return rtf.format(Math.round(seconds / 86400), 'day')
}
function fmt(value: string | null): string {
  return value ? new Date(value).toLocaleString(lang.value === 'ar' ? 'ar-AE' : 'en-AE', { dateStyle: 'medium', timeStyle: 'short' }) : ''
}

// --- actions ----------------------------------------------------------------------------------------

function toggle(row: Row) {
  row.open = !row.open
  row.changed = false
}
function remove(row: Row) {
  if (armed.value !== row.saved.id) {
    armed.value = row.saved.id
    window.setTimeout(() => { if (armed.value === row.saved.id) armed.value = null }, 3000)
    return
  }
  forgetReport(row.saved.id)
  rows.value = rows.value.filter((r) => r.saved.id !== row.saved.id)
  armed.value = null
}
async function copyId(row: Row) {
  try {
    await navigator.clipboard.writeText(row.saved.id)
    copied.value = row.saved.id
    window.setTimeout(() => { copied.value = null }, 1500)
  } catch {
    /* clipboard blocked: the id stays visible to copy by hand */
  }
}

const R = 22
const C = 2 * Math.PI * R
</script>

<template>
  <main class="reports">
    <div class="row-head">
      <div>
        <h1>{{ tr('My reports', 'بلاغاتي') }}</h1>
        <p class="small muted live">
          <span class="dot" :class="{ busy: loading }" />
          <template v-if="loading">{{ tr('Updating…', 'جارٍ التحديث…') }}</template>
          <template v-else-if="loadedAt">{{ tr('Updated', 'آخر تحديث') }} {{ ago(loadedAt) }}</template>
        </p>
      </div>
      <button class="refresh" :disabled="loading" :aria-label="tr('Refresh', 'تحديث')" @click="load">
        <svg viewBox="0 0 24 24" :class="{ spin: loading }" aria-hidden="true"><path d="M20 12a8 8 0 1 1-2.3-5.7M20 4v5h-5" /></svg>
      </button>
    </div>

    <template v-if="rows.length">
      <section class="summary rise">
        <div><b>{{ counts.all }}</b><span>{{ tr('Reports', 'بلاغات') }}</span></div>
        <div class="review"><b>{{ counts.active }}</b><span>{{ tr('In progress', 'قيد المتابعة') }}</span></div>
        <div class="good"><b>{{ counts.confirmed }}</b><span>{{ tr('Confirmed', 'مؤكدة') }}</span></div>
        <div class="good"><b>{{ protectedCount }}</b><span>{{ tr('Times blocked for others', 'مرات حماية الآخرين') }}</span></div>
      </section>

      <div class="chips" role="group" :aria-label="tr('Filter', 'تصفية')">
        <button v-for="[value, en, ar] in FILTERS" :key="value" type="button" class="chip" :aria-pressed="filter === value" @click="filter = value">
          {{ tr(en, ar) }}<span class="n">{{ counts[value] }}</span>
        </button>
      </div>
    </template>

    <section v-else-if="!loading" class="card empty rise">
      <svg viewBox="0 0 64 64" aria-hidden="true"><path d="M14 58V8h26l3 6h11v26H36l-3-6H14" /><path d="M24 22h12M24 28h8" /></svg>
      <h2>{{ tr('No reports yet', 'لا توجد بلاغات بعد') }}</h2>
      <p class="muted">{{ tr('When you report a suspicious link, you can follow it here step by step until police decide.', 'عندما تُبلغ عن رابط مشبوه، يمكنك متابعته هنا خطوة بخطوة حتى تقرر الشرطة.') }}</p>
      <RouterLink to="/" class="button primary">{{ tr('Check a link', 'افحص رابطًا') }}</RouterLink>
    </section>

    <p v-if="rows.length && !visible.length" class="card muted">{{ tr('Nothing here with this filter.', 'لا شيء هنا بهذا التصنيف.') }}</p>

    <TransitionGroup name="list" tag="div" class="list">
      <article v-for="(row, i) in visible" :key="row.saved.id" class="card report" :class="[meta(row).tone, { changed: row.changed }]"
               :style="{ animationDelay: `${i * 60}ms` }">
        <template v-if="row.status">
          <button class="head" :aria-expanded="row.open" @click="toggle(row)">
            <span class="ring" :class="meta(row).tone">
              <svg viewBox="0 0 52 52" aria-hidden="true">
                <circle class="track" cx="26" cy="26" :r="R" />
                <circle class="fill" cx="26" cy="26" :r="R" :stroke-dasharray="C" :stroke-dashoffset="C * (1 - progress(row.status))" />
              </svg>
              <svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path :d="ICON[row.status.status] ?? ICON.sent" /></svg>
            </span>
            <span class="title">
              <span class="domain"><strong>{{ defang(hostOf(row.saved.url)) }}</strong></span>
              <span class="headline">{{ tr(meta(row).en, meta(row).ar) }}</span>
              <span class="small muted">{{ tr('Sent', 'أُرسل') }} {{ ago(row.saved.at) }}<template v-if="row.status.brand"> · {{ row.status.brand }}</template></span>
            </span>
            <span v-if="row.changed" class="badge new">{{ tr('Updated', 'جديد') }}</span>
            <svg class="chev" :class="{ open: row.open }" viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 6 6-6 6" /></svg>
          </button>

          <ol class="stages" :style="{ '--n': stages(row.status).length }">
            <span class="bar"><i :style="{ transform: `scaleX(${current(row.status) / Math.max(1, stages(row.status).length - 1)})` }" /></span>
            <li v-for="(step, k) in stages(row.status)" :key="step.id"
                :class="{ done: step.done, now: k === current(row.status) && !step.done, ghost: !step.done && k > current(row.status), [step.id]: true }">
              <span class="node" />
              <span class="label">{{ short(step) }}</span>
            </li>
          </ol>

          <p class="next">{{ tr(meta(row).nextEn, meta(row).nextAr) }}</p>

          <p v-if="row.status.blocked_count > 0" class="impact">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2.5 4 5.5v6c0 4.7 3.4 9 8 10 4.6-1 8-5.3 8-10v-6l-8-3z" /></svg>
            <span><b>{{ row.status.blocked_count }}</b> {{ tr(row.status.blocked_count === 1 ? 'time this site was blocked for another resident' : 'times this site was blocked for other residents',
                                                              'مرة تم فيها حظر هذا الموقع لحماية سكان آخرين') }}</span>
          </p>

          <div v-if="row.open" class="details rise">
            <ol class="timeline">
              <li v-for="step in row.status.steps" :key="step.id" :class="{ done: step.done }">
                <span>{{ lang === 'ar' ? step.ar : step.en }}</span>
                <span v-if="step.at" class="small muted">{{ fmt(step.at) }}</span>
              </li>
            </ol>
            <div class="actions">
              <button class="small" @click="copyId(row)">{{ copied === row.saved.id ? tr('Copied', 'تم النسخ') : tr('Copy report number', 'انسخ رقم البلاغ') }}</button>
              <button class="small" :class="{ danger: armed === row.saved.id }" @click="remove(row)">
                {{ armed === row.saved.id ? tr('Tap again to remove', 'اضغط مرة أخرى للإزالة') : tr('Remove from this phone', 'إزالة من هذا الهاتف') }}
              </button>
            </div>
            <p class="small muted mono">{{ row.saved.id }}</p>
          </div>
        </template>

        <template v-else-if="row.missing">
          <p class="domain"><strong>{{ defang(hostOf(row.saved.url)) }}</strong></p>
          <p class="muted">{{ tr('This report could not be loaded.', 'تعذّر تحميل هذا البلاغ.') }}</p>
          <button class="small" @click="remove(row)">{{ armed === row.saved.id ? tr('Tap again to remove', 'اضغط مرة أخرى للإزالة') : tr('Remove', 'إزالة') }}</button>
        </template>

        <template v-else>
          <div class="loading"><span class="skeleton ring-s" /><span class="grow"><span class="skeleton line" /><span class="skeleton line short" /></span></div>
          <span class="skeleton bar-s" />
        </template>
      </article>
    </TransitionGroup>
  </main>
</template>

<style scoped>
.row-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; }
.live { display: flex; align-items: center; gap: 0.4rem; margin-top: -0.4rem; }
.dot { width: 0.5rem; height: 0.5rem; border-radius: 50%; background: var(--allow); }
.dot.busy { background: var(--accent); animation: kp-pulse 1s infinite; }
.refresh { min-height: 2.6rem; width: 2.6rem; padding: 0; border-radius: 999px; }
.refresh svg, .chev, .impact svg { width: 1.2rem; height: 1.2rem; fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
.spin { animation: kp-spin 0.9s linear infinite; }

.summary { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0.5rem; margin: 0.5rem 0 0.75rem; }
.summary div { display: grid; gap: 0.1rem; padding: 0.6rem 0.7rem; background: var(--surface); border: 1px solid var(--line); border-radius: 12px; }
.summary b { font-size: 1.35rem; font-variant-numeric: tabular-nums; line-height: 1.1; }
.summary span { font-size: 0.72rem; color: var(--muted); line-height: 1.2; }
.summary .review b { color: var(--warn); }
.summary .good b { color: var(--allow); }
@media (max-width: 420px) { .summary { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
.chips { margin-bottom: 0.85rem; }

.list { display: grid; }
.list-enter-active, .list-leave-active { transition: opacity 260ms ease, transform 260ms cubic-bezier(0.22, 1, 0.36, 1); }
.list-enter-from { opacity: 0; transform: translateY(8px); }
.list-leave-to { opacity: 0; transform: scale(0.97); }
.list-move { transition: transform 260ms cubic-bezier(0.22, 1, 0.36, 1); }

.report { --tone: var(--accent); position: relative; overflow: hidden; animation: kp-rise 360ms cubic-bezier(0.22, 1, 0.36, 1) both; }
.report::before { content: ''; position: absolute; inset-block: 0; inset-inline-start: 0; width: 4px; background: var(--tone); }
.report.review { --tone: var(--warn); }
.report.good { --tone: var(--allow); }
.report.neutral { --tone: var(--dot); }
.report.changed { border-color: var(--tone); animation: kp-rise 360ms both, changed 1.4s 400ms 2; }
@keyframes changed { 0% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--tone) 55%, transparent); } 100% { box-shadow: 0 0 0 10px transparent; } }

.head { display: flex; width: 100%; align-items: center; gap: 0.8rem; padding: 0; min-height: 0; text-align: start; background: none; border: 0; font-weight: 400; }
.title { display: grid; gap: 0.1rem; flex: 1; min-width: 0; }
.title .domain { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.headline { font-weight: 700; color: var(--tone); }
.report.info .headline, .report.neutral .headline { color: var(--text); }
.chev { color: var(--muted); transition: transform 220ms ease; flex: none; }
[dir='rtl'] .chev { transform: scaleX(-1); }
.chev.open { transform: rotate(90deg); }
.badge.new { background: var(--tone); color: var(--on-accent); animation: kp-rise 300ms both; }

.ring { position: relative; flex: none; width: 3.3rem; height: 3.3rem; color: var(--tone); }
.ring.info { color: var(--accent); }
.ring.review { color: var(--warn); }
.ring.good { color: var(--allow); }
.ring.neutral { color: var(--muted); }
.ring svg { width: 100%; height: 100%; }
.ring > svg:first-child { transform: rotate(-90deg); }
[dir='rtl'] .ring > svg:first-child { transform: rotate(-90deg) scaleY(-1); }
.ring circle { fill: none; stroke-width: 4; }
.ring .track { stroke: var(--line); }
.ring .fill { stroke: currentColor; stroke-linecap: round; transition: stroke-dashoffset 900ms cubic-bezier(0.22, 1, 0.36, 1); animation: ring-in 1s cubic-bezier(0.22, 1, 0.36, 1) both; }
@keyframes ring-in { from { stroke-dashoffset: 138.2; } }
.ring .icon { position: absolute; inset: 0; margin: auto; width: 1.35rem; height: 1.35rem; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }

.stages { position: relative; display: grid; grid-template-columns: repeat(var(--n), minmax(0, 1fr)); list-style: none; padding: 0; margin: 1rem 0 0.4rem; }
.bar { position: absolute; top: 0.45rem; inset-inline: calc(50% / var(--n)); height: 3px; border-radius: 3px; background: var(--line); overflow: hidden; }
.bar i { display: block; height: 100%; background: var(--tone); transform-origin: left; transition: transform 900ms cubic-bezier(0.22, 1, 0.36, 1); animation: bar-in 1s cubic-bezier(0.22, 1, 0.36, 1) both; }
[dir='rtl'] .bar i { transform-origin: right; }
@keyframes bar-in { from { transform: scaleX(0); } }
.stages li { position: relative; display: grid; justify-items: center; gap: 0.3rem; text-align: center; }
.node { width: 0.95rem; height: 0.95rem; border-radius: 50%; background: var(--surface); border: 2px solid var(--dot); z-index: 1; transition: background 300ms, border-color 300ms; }
.stages li.done .node { background: var(--tone); border-color: var(--tone); }
.stages li.now .node { border-color: var(--tone); background: var(--surface); animation: kp-pulse 1.4s infinite; box-shadow: 0 0 0 3px color-mix(in srgb, var(--tone) 20%, transparent); }
.stages li.ghost .node { border-style: dashed; }
.stages li.rejected.done .node { background: var(--muted); border-color: var(--muted); }
.label { font-size: 0.68rem; line-height: 1.15; color: var(--muted); }
.stages li.done .label, .stages li.now .label { color: var(--text); font-weight: 600; }
.next { margin: 0.5rem 0 0; font-size: 0.9rem; color: var(--muted); }
.impact { display: flex; align-items: center; gap: 0.5rem; margin: 0.6rem 0 0; padding: 0.5rem 0.7rem; border-radius: 10px; background: var(--allow-soft); color: var(--allow); font-size: 0.88rem; }
.impact b { font-size: 1.05rem; }

.details { margin-top: 0.8rem; padding-top: 0.8rem; border-top: 1px solid var(--line); }
.timeline { list-style: none; padding: 0; margin: 0 0 0.6rem; }
.timeline li { position: relative; padding-inline-start: 1.6rem; padding-bottom: 0.7rem; display: grid; color: var(--muted); }
.timeline li::before { content: ''; position: absolute; inset-inline-start: 0.2rem; top: 0.35rem; width: 0.7rem; height: 0.7rem; border-radius: 50%; border: 2px solid var(--dot); background: var(--surface); }
.timeline li::after { content: ''; position: absolute; inset-inline-start: 0.52rem; top: 1.15rem; bottom: 0; width: 2px; background: var(--line); }
.timeline li:last-child::after { display: none; }
.timeline li.done { color: var(--text); }
.timeline li.done::before { background: var(--tone); border-color: var(--tone); }
.actions { display: flex; gap: 0.5rem; flex-wrap: wrap; }
.actions button { min-height: 2.4rem; font-size: 0.85rem; }
.actions .danger { background: var(--block-soft); color: var(--block); border-color: var(--block); }
.mono { font-family: ui-monospace, Menlo, monospace; direction: ltr; unicode-bidi: isolate; }

.empty { display: grid; justify-items: center; text-align: center; gap: 0.4rem; padding: 2rem 1.2rem; }
.empty svg { width: 4rem; height: 4rem; fill: none; stroke: var(--muted); stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; margin-bottom: 0.4rem; }
.empty .button { margin-top: 0.6rem; }

.loading { display: flex; gap: 0.8rem; align-items: center; }
.ring-s { width: 3.3rem; height: 3.3rem; border-radius: 50%; flex: none; }
.grow { display: grid; gap: 0.4rem; flex: 1; }
.line { height: 0.8rem; }
.line.short { width: 60%; }
.bar-s { display: block; height: 0.6rem; margin-top: 1rem; }
</style>
