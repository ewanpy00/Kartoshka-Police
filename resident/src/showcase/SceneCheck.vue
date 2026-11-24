<script setup lang="ts">
// Scene 2: type a link on Home, press Check; the result screen slides over, the ten sources light up one by
// one, the risk score rolls up and the verdict lands with the real service's button.
import { computed } from 'vue'
import PhoneHome from './PhoneHome.vue'
import Tap from './Tap.vue'
import { roll, span } from './timeline'

const props = defineProps<{ at: number; ar: boolean }>()
const T = (en: string, ar: string) => (props.ar ? ar : en)

const LINK = 'tamm-fines-pay.top'
const TYPE_FROM = 300
const TYPE_TO = 1350
const PRESS = 1550
const SLIDE = 1750
const ROWS = 2000
const typed = computed(() => LINK.slice(0, Math.round(LINK.length * span(props.at, TYPE_FROM, TYPE_TO - TYPE_FROM, (x) => x))))

const SOURCES: [string, string, boolean][] = [
  ['Official list', 'القائمة الرسمية', false], ['Police-confirmed list', 'قائمة الشرطة المؤكدة', true],
  ['Google Safe Browsing', 'التصفح الآمن من Google', true], ['VirusTotal', 'VirusTotal', true], ['Phishing feeds', 'قوائم التصيّد', true],
  ['Domain age', 'عمر النطاق', true], ['First certificate (CT)', 'أول شهادة أمان', true], ['Campaign link', 'ارتباط بحملة', true],
  ['Safe preview', 'المعاينة الآمنة', true], ['AI explanation', 'شرح الذكاء الاصطناعي', true],
]
const R = 26
const C = 2 * Math.PI * R
const score = computed(() => roll(props.at, ROWS + 100, 1200, 94))
const slide = computed(() => span(props.at, SLIDE, 320))
</script>

<template>
  <div class="scene">
    <PhoneHome :ar="ar" :typed="typed" :caret="at > 200 && at < PRESS" :pressed="at >= PRESS && at < PRESS + 180">
      <Tap :at="at" :when="PRESS" />
    </PhoneHome>

    <div v-if="at >= SLIDE" class="result" :style="{ transform: `translateX(${(1 - slide) * (ar ? -100 : 100)}%)` }">
      <div class="status"><span>10:44</span><span>5G<i /></span></div>
      <div class="appbar"><svg class="i" viewBox="0 0 24 24"><path :d="ar ? 'M9 6l6 6-6 6' : 'M15 6l-6 6 6 6'" /></svg>{{ T('Check a link', 'افحص رابطًا') }}</div>
      <div class="pad body">
        <div class="sum">
          <span class="ring">
            <svg viewBox="0 0 64 64"><circle cx="32" cy="32" :r="R" class="track" />
              <circle cx="32" cy="32" :r="R" class="fill" :stroke-dasharray="C" :stroke-dashoffset="C * (1 - score / 100)" /></svg>
            <b>{{ score }}</b>
          </span>
          <span>
            <span class="mono host">tamm-fines-pay[.]top</span><br />
            <span class="small muted">{{ T('Risk score out of 100', 'درجة الخطر من 100') }}</span>
          </span>
        </div>
        <ul class="xray">
          <li v-for="([en, a, hit], i) in SOURCES" :key="en" :class="{ on: at > ROWS + i * 110, hit: hit && at > ROWS + i * 110 }">
            <span class="dot" />{{ T(en, a) }}
            <span class="st">{{ at > ROWS + i * 110 ? (hit ? T('Found', 'وُجد') : T('Clean', 'نظيف')) : '…' }}</span>
          </li>
        </ul>
        <div class="verdict card" :style="{ opacity: span(at, 3300, 300), transform: `translateY(${(1 - span(at, 3300, 360)) * 24}px)` }">
          <p class="h">⚠️ {{ T('Suspected scam', 'احتيال مشتبه به') }}</p>
          <p>{{ T('This page pretends to be TAMM and asks for your card.', 'هذه الصفحة تنتحل صفة «تم» وتطلب بيانات بطاقتك.') }}</p>
          <div class="btn safe" :style="{ opacity: span(at, 3650, 300) }">{{ T('Pay fines on the real TAMM', 'ادفع المخالفات عبر «تم» الرسمي') }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.scene { position: absolute; inset: 0; }
.result { position: absolute; inset: 0; background: var(--bg); z-index: 5; box-shadow: -12px 0 30px rgb(0 0 0 / 0.35); }
.body { display: grid; gap: 10px; padding-top: 12px; }
.sum { display: flex; align-items: center; gap: 14px; line-height: 1.3; }
.host { font-weight: 700; font-size: 15px; }
.ring { position: relative; width: 64px; height: 64px; flex: none; color: var(--block); }
.ring svg { width: 64px; height: 64px; transform: rotate(-90deg); }
.ring circle { fill: none; stroke-width: 6; }
.ring .track { stroke: var(--line); }
.ring .fill { stroke: currentColor; stroke-linecap: round; }
.ring b { position: absolute; inset: 0; display: grid; place-items: center; font-size: 20px; font-variant-numeric: tabular-nums; }
.xray { list-style: none; margin: 0; padding: 0; display: grid; gap: 4px; }
.xray li { display: flex; align-items: center; gap: 9px; height: 29px; padding: 0 12px; border-radius: 9px; background: var(--surface); border: 1px solid var(--line);
  font-size: 13px; color: var(--muted); transition: color 200ms, border-color 200ms; }
.xray .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--dot); transition: background 200ms, box-shadow 200ms; }
.xray .st { margin-inline-start: auto; font-weight: 700; font-size: 12px; }
.xray li.on { color: var(--text); }
.xray li.on .dot { background: var(--allow); }
.xray li.on .st { color: var(--allow); }
.xray li.hit .dot { background: var(--block); box-shadow: 0 0 7px var(--block); }
.xray li.hit .st { color: var(--block); }
.verdict { border-color: var(--block); background: var(--block-soft); display: grid; gap: 8px; }
.verdict .h { font-size: 19px; font-weight: 800; color: var(--block); }
.verdict p { font-size: 14px; }
</style>
