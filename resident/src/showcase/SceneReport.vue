<script setup lang="ts">
// Scene 3: report the link to police, then My reports as a time-lapse: the tracker walks from "sent" to
// "site taken down", the ring fills, each change flashes "Updated", and the protected-residents count rolls up.
import { computed } from 'vue'
import Tap from './Tap.vue'
import { roll, span } from './timeline'

const props = defineProps<{ at: number; ar: boolean }>()
const T = (en: string, ar: string) => (props.ar ? ar : en)

const NOTE = 'SMS from AD-FINES'
const NOTE_AR = 'رسالة من AD-FINES'
const TAP = 850
const SENT = 1000
const SWITCH = 1300
const STEPS: { id: string; at: number; en: string; ar: string; short: [string, string]; time: [string, string] }[] = [
  { id: 'sent', at: 1500, en: 'We received your report', ar: 'استلمنا بلاغك', short: ['Sent', 'أُرسل'], time: ['10:45', '10:45'] },
  { id: 'checked', at: 1950, en: 'The link has been checked', ar: 'تم فحص الرابط', short: ['Checked', 'فُحص'], time: ['10:46', '10:46'] },
  { id: 'review', at: 2450, en: 'A police officer is reviewing it', ar: 'يراجعه ضابط شرطة الآن', short: ['Review', 'مراجعة'], time: ['11:20', '11:20'] },
  { id: 'confirmed', at: 3050, en: 'Confirmed as a scam and blocked', ar: 'تأكد أنه احتيال وتم حظره', short: ['Confirmed', 'مؤكد'], time: ['14:05', '14:05'] },
  { id: 'down', at: 3650, en: 'The site has been taken down', ar: 'تم إيقاف الموقع', short: ['Taken down', 'أُوقف'], time: ['Tomorrow 09:30', 'غدًا 09:30'] },
]
const LONG: Record<string, [string, string]> = {
  sent: ['Report sent', 'تم إرسال البلاغ'], checked: ['Checked: high risk', 'تم الفحص: خطر مرتفع'], review: ['In police review', 'قيد مراجعة الشرطة'],
  confirmed: ['Confirmed by police', 'أكدته الشرطة'], down: ['Site taken down', 'تم إيقاف الموقع'],
}
const reached = computed(() => STEPS.filter((s) => props.at >= s.at).length)
const step = computed(() => STEPS[Math.max(0, reached.value - 1)])
const tone = computed(() => (reached.value >= 4 ? 'good' : reached.value === 3 ? 'review' : 'info'))
const flash = computed(() => STEPS.some((s, i) => i > 0 && props.at >= s.at && props.at < s.at + 450))
const R = 24
const C = 2 * Math.PI * R
// The ring and bar ease between stages through their CSS transitions.
const progress = computed(() => reached.value / STEPS.length)
const noteTyped = computed(() => {
  const text = props.ar ? NOTE_AR : NOTE
  return text.slice(0, Math.round(text.length * span(props.at, 120, 550, (x) => x)))
})
</script>

<template>
  <div class="scene">
    <!-- Report to police -->
    <div class="report" :style="{ opacity: 1 - span(at, SWITCH, 250) }">
      <div class="status"><span>10:45</span><span>5G<i /></span></div>
      <div class="appbar"><svg class="i" viewBox="0 0 24 24"><path :d="ar ? 'M9 6l6 6-6 6' : 'M15 6l-6 6 6 6'" /></svg>{{ T('Check a link', 'افحص رابطًا') }}</div>
      <div class="pad body">
        <div class="card mini"><span class="badge block">⚠️ {{ T('Suspected scam', 'احتيال مشتبه به') }}</span><span class="mono">tamm-fines-pay[.]top</span></div>
        <div class="card">
          <b class="h">{{ T('Report to police', 'أبلغ الشرطة') }}</b>
          <p class="small muted">{{ T('Where did you get this link?', 'من أين وصلك هذا الرابط؟') }}</p>
          <div class="area">{{ noteTyped }}</div>
          <div v-if="at < SENT" class="btn" :class="{ pressed: at >= TAP && at < TAP + 160 }">
            <svg class="i" viewBox="0 0 24 24"><path d="M5 21V4h9l1 2h4v9h-6l-1-2H5" /></svg>{{ T('Report', 'أبلغ') }}<Tap :at="at" :when="TAP" />
          </div>
          <div v-else class="sent" :style="{ transform: `scale(${0.92 + 0.08 * span(at, SENT, 250)})` }">
            <svg class="i" viewBox="0 0 24 24"><path d="M20 6 9 17l-5-5" /></svg>
            <span>{{ T('Report KP-7Q4M2D sent', 'تم إرسال البلاغ KP-7Q4M2D') }}<br /><span class="small">{{ T('Follow it in My reports', 'تابعه في بلاغاتي') }}</span></span>
          </div>
        </div>
      </div>
    </div>

    <!-- My reports -->
    <div v-if="at >= SWITCH" class="reports" :style="{ opacity: span(at, SWITCH, 300), transform: `translateY(${(1 - span(at, SWITCH, 360)) * 20}px)` }">
      <div class="status"><span>10:45</span><span>5G<i /></span></div>
      <div class="pad body">
        <div class="titlerow">
          <span><b class="t">{{ T('My reports', 'بلاغاتي') }}</b><br /><span class="small muted live"><i />{{ T('Updated now', 'آخر تحديث الآن') }}</span></span>
          <span class="lapse small">⏱ {{ T('1 day in 3 seconds', 'يوم في 3 ثوانٍ') }}</span>
        </div>

        <div class="card track" :class="[tone, { flash }]">
          <div class="head">
            <span class="ring">
              <svg viewBox="0 0 56 56"><circle cx="28" cy="28" :r="R" class="tr" /><circle cx="28" cy="28" :r="R" class="fi" :stroke-dasharray="C" :stroke-dashoffset="C * (1 - progress)" /></svg>
              <svg class="ic" viewBox="0 0 24 24"><path :d="reached >= 4 ? 'M12 2.5 4 5.5v6c0 4.7 3.4 9 8 10 4.6-1 8-5.3 8-10v-6l-8-3zM8.5 12l2.5 2.5 4.5-5' : reached === 3 ? 'M2.5 12S6 5 12 5s9.5 7 9.5 7-3.5 7-9.5 7-9.5-7-9.5-7zM12 9a3 3 0 1 1 0 6 3 3 0 0 1 0-6z' : 'M3 11.5 21 3l-7.5 18-2.5-7.5L3 11.5z'" /></svg>
            </span>
            <span class="tt">
              <span class="mono"><b>tamm-fines-pay[.]top</b></span>
              <span class="hl">{{ T(step.en, step.ar) }}</span>
              <span class="small muted">{{ T('Sent today · TAMM', 'أُرسل اليوم · تم') }}</span>
            </span>
            <span v-if="flash" class="upd">{{ T('Updated', 'جديد') }}</span>
          </div>
          <ol class="stages">
            <span class="bar"><i :style="{ transform: `scaleX(${Math.max(0, reached - 1) / (STEPS.length - 1)})` }" /></span>
            <li v-for="(s, i) in STEPS" :key="s.id" :class="{ done: i < reached, now: i === reached }">
              <span class="node" /><span class="lb">{{ T(s.short[0], s.short[1]) }}</span>
            </li>
          </ol>
          <p v-if="reached >= 4" class="impact" :style="{ opacity: span(at, STEPS[3].at, 300) }">
            <svg class="i" viewBox="0 0 24 24"><path d="M12 2.5 4 5.5v6c0 4.7 3.4 9 8 10 4.6-1 8-5.3 8-10v-6l-8-3z" /></svg>
            <span><b>{{ roll(at, STEPS[3].at + 100, 1100, 37) }}</b> {{ T('times blocked for other residents', 'مرة تم حظره لحماية سكان آخرين') }}</span>
          </p>
        </div>

        <div class="card">
          <ol class="timeline">
            <li v-for="s in STEPS" :key="s.id" :class="{ done: at >= s.at }" :style="{ opacity: at >= s.at ? span(at, s.at, 250) : 0.35 }">
              <span>{{ T(LONG[s.id][0], LONG[s.id][1]) }}</span><span class="small muted">{{ at >= s.at ? T(s.time[0], s.time[1]) : '' }}</span>
            </li>
          </ol>
        </div>
      </div>
      <div class="tabs">
        <span><svg class="i" viewBox="0 0 24 24"><path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z" /></svg>{{ T('Home', 'الرئيسية') }}</span>
        <span class="on"><svg class="i" viewBox="0 0 24 24"><path d="M5 21V4h9l1 2h4v9h-6l-1-2H5" /></svg>{{ T('Reports', 'بلاغاتي') }}</span>
        <span><svg class="i" viewBox="0 0 24 24"><path d="M12 12 19 5M21 12a9 9 0 1 1-9-9M17 12a5 5 0 1 1-5-5" /></svg>{{ T('Radar', 'الرادار') }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.scene, .report, .reports { position: absolute; inset: 0; }
.reports { background: var(--bg); }
.body { display: grid; gap: 12px; padding-top: 12px; }
.mini { display: flex; align-items: center; gap: 10px; padding: 10px 12px; font-size: 13.5px; }
.h { display: block; font-size: 17px; }
.area { height: 64px; margin: 8px 0 10px; padding: 10px 12px; border: 1px solid var(--line); border-radius: 12px; font-size: 14px; }
.btn { position: relative; transition: transform 120ms; }
.btn.pressed { transform: scale(0.97); }
.sent { display: flex; align-items: center; gap: 10px; padding: 10px 14px; border-radius: 12px; background: var(--allow-soft); color: var(--allow); font-weight: 700; line-height: 1.3; }
.sent .small { font-weight: 500; }

.titlerow { display: flex; justify-content: space-between; align-items: center; }
.t { font-size: 23px; }
.live { display: inline-flex; align-items: center; gap: 6px; }
.live i { width: 7px; height: 7px; border-radius: 50%; background: var(--allow); }
.lapse { padding: 4px 10px; border-radius: 999px; background: var(--grey-soft); color: var(--accent); font-weight: 700; }

.track { --tone: var(--accent); position: relative; overflow: hidden; transition: border-color 300ms, box-shadow 300ms; }
.track::before { content: ''; position: absolute; inset-block: 0; inset-inline-start: 0; width: 4px; background: var(--tone); transition: background 300ms; }
.track.review { --tone: var(--warn); }
.track.good { --tone: var(--allow); }
.track.flash { border-color: var(--tone); box-shadow: 0 0 0 4px color-mix(in srgb, var(--tone) 25%, transparent); }
.head { display: flex; align-items: center; gap: 12px; }
.ring { position: relative; width: 56px; height: 56px; flex: none; color: var(--tone); }
.ring svg { width: 56px; height: 56px; transform: rotate(-90deg); }
.ring circle { fill: none; stroke-width: 4.5; }
.ring .tr { stroke: var(--line); }
.ring .fi { stroke: currentColor; stroke-linecap: round; transition: stroke-dashoffset 450ms cubic-bezier(0.22, 1, 0.36, 1); }
.ring .ic { position: absolute; inset: 0; margin: auto; width: 24px; height: 24px; transform: none; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
.tt { display: grid; gap: 1px; flex: 1; min-width: 0; line-height: 1.3; }
.tt .mono { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hl { font-weight: 800; color: var(--tone); }
.track.info .hl { color: var(--text); }
.upd { padding: 2px 8px; border-radius: 999px; background: var(--tone); color: var(--bg); font-size: 11px; font-weight: 800; align-self: flex-start; }
.stages { position: relative; display: grid; grid-template-columns: repeat(5, 1fr); list-style: none; padding: 0; margin: 16px 0 4px; }
.bar { position: absolute; top: 7px; inset-inline: 10%; height: 3px; border-radius: 3px; background: var(--line); overflow: hidden; }
.bar i { display: block; height: 100%; background: var(--tone); transform-origin: left; transition: transform 450ms cubic-bezier(0.22, 1, 0.36, 1), background 300ms; }
[dir='rtl'] .bar i { transform-origin: right; }
.stages li { display: grid; justify-items: center; gap: 5px; text-align: center; }
.node { width: 16px; height: 16px; border-radius: 50%; background: var(--surface); border: 2px dashed var(--dot); z-index: 1; transition: all 300ms; }
.stages li.done .node { background: var(--tone); border: 2px solid var(--tone); }
.stages li.now .node { border: 2px solid var(--tone); box-shadow: 0 0 0 4px color-mix(in srgb, var(--tone) 22%, transparent); }
.lb { font-size: 10.5px; color: var(--muted); line-height: 1.1; }
.stages li.done .lb, .stages li.now .lb { color: var(--text); font-weight: 700; }
.impact { display: flex; align-items: center; gap: 8px; margin-top: 10px !important; padding: 8px 10px; border-radius: 10px; background: var(--allow-soft); color: var(--allow); font-size: 13px; }
.impact b { font-size: 17px; font-variant-numeric: tabular-nums; }
.timeline { list-style: none; margin: 0; padding: 0; display: grid; gap: 9px; }
.timeline li { position: relative; display: flex; justify-content: space-between; gap: 8px; padding-inline-start: 22px; font-size: 13.5px; }
.timeline li::before { content: ''; position: absolute; inset-inline-start: 2px; top: 4px; width: 10px; height: 10px; border-radius: 50%; border: 2px solid var(--dot); }
.timeline li.done::before { background: var(--allow); border-color: var(--allow); }
</style>
