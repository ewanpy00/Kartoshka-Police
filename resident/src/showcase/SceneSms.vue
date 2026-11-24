<script setup lang="ts">
// Scene 1: a scam SMS, the tap on its link, Gatekeeper's half-second check, the block page.
import { computed } from 'vue'
import Tap from './Tap.vue'
import { roll, span } from './timeline'

const props = defineProps<{ at: number; ar: boolean }>()
const T = (en: string, ar: string) => (props.ar ? ar : en)

const TAP = 1300
const CHECK = 1600
const BLOCK = 2450
const checking = computed(() => props.at >= CHECK && props.at < BLOCK + 300)
const blocked = computed(() => props.at >= BLOCK)
const SOURCES: [string, string][] = [['Police-confirmed list', 'قائمة الشرطة'], ['Lookalike of RTA', 'يشبه هيئة الطرق'], ['Domain age: 2 days', 'عمر النطاق: يومان']]
const REASONS: [string, string][] = [
  ['The address imitates RTA but is not theirs', 'العنوان يقلّد هيئة الطرق لكنه ليس تابعًا لها'],
  ['Registered 2 days ago', 'سُجّل قبل يومين'],
  ['Asks for your card and a one-time code', 'يطلب بطاقتك ورمز التحقق'],
]
</script>

<template>
  <div class="sms">
    <!-- Messages -->
    <div class="status"><span>10:42</span><span>5G<i /></span></div>
    <div class="appbar">
      <svg class="i" viewBox="0 0 24 24"><path d="M15 6l-6 6 6 6" /></svg>
      <span class="av">AD</span>
      <span><b>AD-FINES</b><br /><span class="small muted">{{ T('Text message', 'رسالة نصية') }}</span></span>
    </div>
    <div class="thread pad">
      <p class="when small muted">{{ T('Today 10:41', 'اليوم 10:41') }}</p>
      <div class="bubble" :style="{ opacity: span(at, 200, 400), transform: `translateY(${(1 - span(at, 200, 400)) * 14}px)` }">
        <p>{{ T('RTA: You have an unpaid traffic fine of AED 150. Pay today to avoid a penalty:', 'هيئة الطرق: لديك مخالفة مرورية غير مدفوعة بقيمة 150 درهمًا. ادفع اليوم لتجنّب الغرامة:') }}</p>
        <p class="link" :class="{ pressed: at >= TAP && at < TAP + 300 }"><span class="mono">https://rta-fine-ae.xyz/pay</span><Tap :at="at" :when="TAP" /></p>
      </div>
    </div>

    <!-- Gatekeeper is checking -->
    <div v-if="checking" class="checking" :style="{ opacity: span(at, CHECK, 220) * (1 - span(at, BLOCK, 300)) }">
      <div class="ring"><i :style="{ transform: `scale(${1 + ((at - CHECK) % 700) / 700 * 0.6})`, opacity: 1 - ((at - CHECK) % 700) / 700 }" />
        <svg viewBox="0 0 24 24"><path d="M12 2.5 4 5.5v6c0 4.7 3.4 9 8 10 4.6-1 8-5.3 8-10v-6l-8-3z" /></svg></div>
      <p class="h">{{ T('Checking link…', 'جارٍ فحص الرابط…') }}</p>
      <p class="mono muted">rta-fine-ae[.]xyz</p>
      <ul>
        <li v-for="([en, a], i) in SOURCES" :key="en" :class="{ hit: at > CHECK + 200 + i * 180 }">
          <span class="dot" />{{ T(en, a) }}
        </li>
      </ul>
      <p class="ms small muted">{{ roll(at, CHECK, BLOCK - CHECK, 380) }} ms</p>
    </div>

    <!-- Block page -->
    <div v-if="blocked" class="block" :style="{ opacity: span(at, BLOCK, 260) }">
      <div class="status"><span>10:42</span><span>5G<i /></span></div>
      <div class="hero">
        <span class="shield" :style="{ transform: `scale(${0.4 + 0.6 * span(at, BLOCK + 100, 420)})` }">
          <svg viewBox="0 0 24 24"><path d="M12 2.5 4 5.5v6c0 4.7 3.4 9 8 10 4.6-1 8-5.3 8-10v-6l-8-3z" /><path d="m9.5 9.5 5 5M14.5 9.5l-5 5" /></svg>
        </span>
        <h3>{{ T('Scam site blocked', 'تم حظر موقع احتيال') }}</h3>
        <p class="mono">rta-fine-ae[.]xyz</p>
      </div>
      <div class="pad body">
        <div class="card">
          <p class="lead">{{ T('This page pretends to be RTA.', 'هذه الصفحة تنتحل صفة هيئة الطرق.') }}</p>
          <ul class="reasons">
            <li v-for="([en, a], i) in REASONS" :key="en" :style="{ opacity: span(at, BLOCK + 350 + i * 160, 260), transform: `translateX(${(1 - span(at, BLOCK + 350 + i * 160, 260)) * (ar ? -10 : 10)}px)` }">
              {{ T(en, a) }}</li>
          </ul>
        </div>
        <div class="btn safe" :style="{ opacity: span(at, BLOCK + 850, 300) }">
          <svg class="i" viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6" /></svg>{{ T('Open the real RTA app', 'افتح تطبيق هيئة الطرق الرسمي') }}</div>
        <div class="btn ghost" :style="{ opacity: span(at, BLOCK + 950, 300) }">{{ T('Go back', 'رجوع') }}</div>
        <p class="count small" :style="{ opacity: span(at, BLOCK + 1150, 300) }">
          <b>{{ 17 + (at > BLOCK + 1250 ? 1 : 0) }}</b> {{ T('scams blocked on this phone', 'احتيال تم حظره على هذا الهاتف') }}</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.sms { position: absolute; inset: 0; }
.av { display: grid; place-items: center; width: 36px; height: 36px; border-radius: 50%; background: var(--grey-soft); font-size: 13px; font-weight: 700; }
.appbar b { font-size: 15px; }
.appbar > span:last-child { line-height: 1.15; font-size: 14px; }
.thread { padding-top: 18px; }
.when { text-align: center; margin-bottom: 12px; }
.bubble { max-width: 290px; padding: 12px 14px; border-radius: 18px; border-end-start-radius: 4px; background: var(--grey-soft); display: grid; gap: 6px; font-size: 15px; }
.link { position: relative; color: #7cb4ff; text-decoration: underline; justify-self: start; padding: 2px 4px; margin-inline-start: -4px; border-radius: 6px; transition: background 120ms; }
.ph.light .link { color: #1a5fd0; }
.link.pressed { background: rgb(124 180 255 / 0.25); }

.checking { position: absolute; inset: 0; display: grid; place-content: center; justify-items: center; gap: 10px; background: var(--hero); color: #fff; z-index: 10; }
.ring { position: relative; width: 96px; height: 96px; display: grid; place-items: center; margin-bottom: 8px; }
.ring i { position: absolute; inset: 0; border-radius: 50%; border: 2px solid #d7b14e; }
.ring svg { width: 52px; height: 52px; fill: #d7b14e; }
.checking .h { font-size: 20px; font-weight: 700; }
.checking ul { list-style: none; padding: 0; margin: 10px 0 0; display: grid; gap: 7px; font-size: 13.5px; color: #b9c0cc; }
.checking li { display: flex; align-items: center; gap: 8px; transition: color 200ms; }
.checking .dot { width: 9px; height: 9px; border-radius: 50%; background: #3a4560; transition: background 200ms, box-shadow 200ms; }
.checking li.hit { color: #fff; }
.checking li.hit .dot { background: #ff9483; box-shadow: 0 0 8px #ff9483; }
.ms { margin-top: 6px; font-variant-numeric: tabular-nums; }

.block { position: absolute; inset: 0; background: var(--bg); z-index: 11; }
.block > .status { position: absolute; inset-inline: 0; top: 0; color: #fff; z-index: 1; }
.hero { padding: 54px 20px 26px; display: grid; justify-items: center; gap: 6px; text-align: center; color: #fff;
  background: linear-gradient(160deg, #b32416, #7d160c); border-radius: 0 0 26px 26px; }
.shield { display: grid; place-items: center; width: 78px; height: 78px; border-radius: 50%; background: rgb(255 255 255 / 0.14); margin-bottom: 6px; }
.shield svg { width: 44px; height: 44px; fill: none; stroke: #fff; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
.hero h3 { margin: 0; font-size: 23px; }
.hero .mono { opacity: 0.85; font-size: 13.5px; }
.body { display: grid; gap: 10px; margin-top: -14px; }
.lead { font-weight: 700; margin-bottom: 8px; }
.reasons { margin: 0; padding-inline-start: 18px; display: grid; gap: 5px; font-size: 13.5px; color: var(--muted); }
.count { text-align: center; color: var(--muted); margin-top: 2px; }
.count b { color: var(--block); font-size: 15px; }
</style>
