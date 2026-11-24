<script setup lang="ts">
// Scene 4: the scam radar fills in (counters roll, the bars by kind of scam grow), the RTA card slides in,
// then a new police-confirmed site arrives live and bumps the numbers.
import { computed } from 'vue'
import { roll, span } from './timeline'

const props = defineProps<{ at: number; ar: boolean }>()
const T = (en: string, ar: string) => (props.ar ? ar : en)

const LIVE = 2700
const bump = computed(() => (props.at >= LIVE ? 1 : 0))
const KINDS: { en: string; ar: string; n: number; today: number; icon: string }[] = [
  { en: 'Government', ar: 'خدمات حكومية', n: 118, today: 22, icon: 'M3 9.5 12 4l9 5.5M5 10v8M9.5 10v8M14.5 10v8M19 10v8M3 20.5h18' },
  { en: 'Parcels', ar: 'الطرود', n: 58, today: 11, icon: 'M12 3 3.5 7.5v9L12 21l8.5-4.5v-9L12 3zM3.5 7.5 12 12l8.5-4.5M12 12v9' },
  { en: 'ID & sign-in', ar: 'الهوية والدخول', n: 32, today: 4, icon: 'M4 5h16v14H4zM9 9.5a2 2 0 1 1 0 4 2 2 0 0 1 0-4zM14.5 10h3.5M14.5 13.5h3.5' },
  { en: 'Police & fines', ar: 'الشرطة والمخالفات', n: 19, today: 3, icon: 'M12 2.5 4 5.5v6c0 4.7 3.4 9 8 10 4.6-1 8-5.3 8-10v-6l-8-3zM12 8v5M12 16h.01' },
]
</script>

<template>
  <div class="scene">
    <div class="status"><span>10:47</span><span>5G<i /></span></div>
    <div v-if="at >= LIVE && at < LIVE + 1300" class="toast" :style="{ opacity: span(at, LIVE, 200) * (1 - span(at, LIVE + 1000, 300)), transform: `translateY(${(1 - span(at, LIVE, 300)) * -30}px)` }">
      <span class="pulse" /><span><b>{{ T('New fake site confirmed', 'تأكيد موقع مزيف جديد') }}</b><br /><span class="mono small">rta-pay[.]top · RTA</span></span>
    </div>
    <div class="pad body">
      <div><b class="t">{{ T('Scam radar', 'رادار الاحتيال') }}</b><br /><span class="small muted live"><i />{{ T('Last 7 days · live', 'آخر 7 أيام · مباشر') }}</span></div>
      <div class="sum">
        <div class="hot"><b>{{ roll(at, 0, 1000, 256) + bump }}</b><span>{{ T('Active scam sites', 'مواقع احتيال نشطة') }}</span></div>
        <div class="warm"><b>{{ roll(at, 100, 1000, 40) + bump }} <i class="up" /></b><span>{{ T('New today', 'جديد اليوم') }}</span></div>
        <div><b>{{ roll(at, 200, 1000, 172) + bump }}</b><span>{{ T('Confirmed by police', 'أكدتها الشرطة') }}</span></div>
        <div class="soft"><b>{{ roll(at, 300, 1000, 84) }}</b><span>{{ T('Suspected', 'مشتبه بها') }}</span></div>
      </div>
      <div class="card kinds">
        <b class="h">{{ T('What scammers imitate now', 'ما يقلّده المحتالون الآن') }}</b>
        <div v-for="(k, i) in KINDS" :key="k.en" class="kind" :style="{ opacity: span(at, 400 + i * 140, 300) }">
          <span class="ki"><svg class="i" viewBox="0 0 24 24"><path :d="k.icon" /></svg></span>
          <span class="kb">
            <span class="kl"><b>{{ T(k.en, k.ar) }}</b><span><b>{{ k.n + (i === 0 ? bump : 0) }}</b> <bdi class="plus">+{{ k.today + (i === 0 ? bump : 0) }}</bdi></span></span>
            <span class="bar"><i :style="{ transform: `scaleX(${(k.n / 118) * span(at, 500 + i * 140, 700)})` }" /></span>
          </span>
        </div>
      </div>
      <div class="card brand" :class="{ grew: at >= LIVE && at < LIVE + 1200 }" :style="{ opacity: span(at, 1700, 300), transform: `translateY(${(1 - span(at, 1700, 380)) * 26}px)` }">
        <div class="bh">
          <span class="av">RT</span>
          <span class="bt"><b>RTA</b><br /><span class="small muted">{{ 66 + bump }} {{ T('active', 'نشط') }} · <bdi class="plus">+{{ 13 + bump }} {{ T('today', 'اليوم') }}</bdi></span></span>
          <span v-if="at >= LIVE" class="badge new">+1 {{ T('new', 'جديد') }}</span>
          <span v-else class="badge block">▲ +4</span>
        </div>
        <div class="stack" :style="{ width: `${100 * span(at, 1900, 600)}%` }"><i class="c" style="flex-grow: 48" /><i class="s" :style="{ flexGrow: 18 + bump }" /></div>
        <p class="tip small" :style="{ opacity: span(at, 2200, 300) }">💡 {{ T('RTA never sends fine links by SMS. Check fines in the RTA app.', 'لا ترسل الهيئة روابط المخالفات عبر الرسائل. تحقّق في تطبيق الهيئة.') }}</p>
      </div>
    </div>
    <div class="tabs">
      <span><svg class="i" viewBox="0 0 24 24"><path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z" /></svg>{{ T('Home', 'الرئيسية') }}</span>
      <span><svg class="i" viewBox="0 0 24 24"><path d="M5 21V4h9l1 2h4v9h-6l-1-2H5" /></svg>{{ T('Reports', 'بلاغاتي') }}</span>
      <span class="on"><svg class="i" viewBox="0 0 24 24"><path d="M12 12 19 5M21 12a9 9 0 1 1-9-9M17 12a5 5 0 1 1-5-5" /></svg>{{ T('Radar', 'الرادار') }}</span>
    </div>
  </div>
</template>

<style scoped>
.scene { position: absolute; inset: 0; }
.body { display: grid; gap: 11px; padding-top: 10px; }
.t { font-size: 23px; }
.live { display: inline-flex; align-items: center; gap: 6px; }
.live i { width: 7px; height: 7px; border-radius: 50%; background: var(--allow); box-shadow: 0 0 6px var(--allow); }
.sum { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.sum div { display: grid; padding: 9px 12px; border-radius: 13px; background: var(--surface); border: 1px solid var(--line); }
.sum b { display: flex; align-items: center; gap: 6px; font-size: 23px; font-variant-numeric: tabular-nums; line-height: 1.15; }
.sum span { font-size: 11.5px; color: var(--muted); }
.sum .hot b { color: var(--block); }
.sum .warm b { color: var(--warn); }
.sum .soft b { color: var(--muted); }
.up { width: 0; height: 0; border-inline: 6px solid transparent; border-bottom: 8px solid var(--block); }
.kinds { display: grid; gap: 9px; }
.h { font-size: 15px; }
.kind { display: flex; gap: 10px; align-items: center; }
.ki { display: grid; place-items: center; width: 34px; height: 34px; border-radius: 10px; background: var(--block-soft); color: var(--block); flex: none; }
.ki .i { width: 17px; height: 17px; }
.kb { display: grid; gap: 5px; flex: 1; }
.kl { display: flex; justify-content: space-between; font-size: 13.5px; }
.kl > span > b { font-variant-numeric: tabular-nums; }
.plus { color: var(--warn); font-weight: 700; font-size: 12.5px; }
.bar { height: 6px; border-radius: 6px; background: var(--grey-soft); overflow: hidden; }
.bar i { display: block; height: 100%; border-radius: 6px; background: linear-gradient(90deg, var(--warn), var(--block)); transform-origin: left; }
[dir='rtl'] .bar i { transform-origin: right; }
.brand { position: relative; overflow: hidden; border-inline-start: 4px solid var(--block); transition: box-shadow 300ms; }
.brand.grew { box-shadow: 0 0 0 4px color-mix(in srgb, var(--block) 30%, transparent); }
.bh { display: flex; align-items: center; gap: 11px; line-height: 1.3; }
.av { display: grid; place-items: center; width: 42px; height: 42px; border-radius: 50%; font-weight: 800; color: var(--block);
  background: color-mix(in srgb, var(--block) 14%, var(--surface)); border: 2px solid color-mix(in srgb, var(--block) 45%, transparent); flex: none; }
.bt { flex: 1; }
.bt b { font-size: 16px; }
.badge.new { background: var(--block); color: var(--bg); }
.stack { display: flex; gap: 2px; height: 8px; margin: 12px 0 8px; border-radius: 8px; overflow: hidden; }
.stack i { display: block; flex-basis: 0; }
.c { background: var(--block); }
.s { background: var(--warn); }
.tip { padding: 8px 10px; border-radius: 10px; background: var(--grey-soft); }
.toast { position: absolute; top: 40px; inset-inline: 14px; z-index: 20; display: flex; gap: 10px; align-items: center; padding: 10px 14px; border-radius: 14px;
  background: var(--surface); border: 1px solid var(--block); box-shadow: 0 10px 30px rgb(0 0 0 / 0.4); line-height: 1.3; font-size: 13.5px; }
.pulse { width: 10px; height: 10px; border-radius: 50%; background: var(--block); box-shadow: 0 0 0 0 var(--block); animation: pulse 1s infinite; flex: none; }
@keyframes pulse { to { box-shadow: 0 0 0 10px transparent; } }
</style>
