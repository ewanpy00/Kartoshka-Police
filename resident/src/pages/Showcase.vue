<script setup lang="ts">
// Product tour for a live presentation (/showcase): every resident feature played as a scripted, looping
// animation in about 24 s, styled after the console's /live wall (ink and gold, dark stage). Nothing here
// calls the API; the screens are drawn from fixed sample data and the page says so.
// ?phone shows only the phone screen, full window, for a screen recording on a phone (the Gatekeeper tour
// mode opens this) or a vertical video export. ?light draws the phone screens in the light theme (the APK's
// tour passes it unless it is asked for dark).
// Keys: Space pause, ← → previous/next scene, R restart, L language, F full screen.
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { lang, tr } from '../i18n'
import '../showcase/phone.css'
import PhoneScreen from '../showcase/PhoneScreen.vue'
import { SCENES, TOTAL, span, useTimeline, type SceneId } from '../showcase/timeline'

// `phone` is set by the offline tour in the Gatekeeper APK (showcase/tour-main.ts); options also come as #t=…
// there, because the app opens it from a file.
const props = defineProps<{ phone?: boolean }>()
const query = new URLSearchParams(location.search + '&' + location.hash.slice(1))

const { t, playing, scene, local, seek, jump, toggle, restart } = useTimeline()
const light = query.has('light') || query.get('theme') === 'light'
const ar = computed(() => lang.value === 'ar')
// ?once plays the tour a single time and holds the end card (for a screen recording), instead of looping.
if (query.has('once')) watch(t, (now, before) => { if (now < before && playing.value) { seek(TOTAL - 1); playing.value = false } })

const CHAPTERS: { id: SceneId; en: string; ar: string; bodyEn: string; bodyAr: string }[] = [
  { id: 'sms', en: 'Blocks the scam before it opens', ar: 'يوقف الاحتيال قبل أن يُفتح',
    bodyEn: 'Gatekeeper is the default browser: a link from an SMS is checked in under half a second, and a scam page never loads.',
    bodyAr: 'الحارس هو المتصفح الافتراضي: يُفحص رابط الرسالة في أقل من نصف ثانية، ولا تُفتح صفحة الاحتيال أبدًا.' },
  { id: 'check', en: 'Checks any link', ar: 'يفحص أي رابط',
    bodyEn: 'Paste it on Home. Ten sources, from the police list to AI, give one clear answer and the real service.',
    bodyAr: 'الصقه في الرئيسية. عشرة مصادر، من قائمة الشرطة إلى الذكاء الاصطناعي، تعطي جوابًا واضحًا والخدمة الرسمية.' },
  { id: 'report', en: 'Report it and follow it', ar: 'أبلغ وتابع',
    bodyEn: 'One tap sends it to police. The tracker shows every step until the site is taken down, and how many residents it protected.',
    bodyAr: 'ضغطة واحدة ترسله إلى الشرطة. يعرض المتتبّع كل خطوة حتى إيقاف الموقع، وعدد السكان الذين حماهم.' },
  { id: 'radar', en: 'Scam radar', ar: 'رادار الاحتيال',
    bodyEn: 'What scammers imitate right now, by brand and kind of scam, updated live.',
    bodyAr: 'ما يقلّده المحتالون الآن، حسب الجهة ونوع الاحتيال، بتحديث مباشر.' },
  { id: 'lang', en: 'Arabic and English, light and dark', ar: 'العربية والإنجليزية، فاتح وداكن',
    bodyEn: 'Follows the phone, or pick it in Settings.', bodyAr: 'يتبع إعدادات الهاتف، أو اختره من الإعدادات.' },
]
const sceneOf = (id: SceneId) => SCENES.find((s) => s.id === id)!
const progressOf = (id: SceneId) => {
  const s = sceneOf(id)
  return Math.min(1, Math.max(0, (t.value - s.start) / (s.end - s.start)))
}

// The phone: drawn at 375 x 790 and scaled to the stage height.
const scale = ref(1)
const capture = ref(false)
const solo = props.phone || query.has('phone')
// Phone only: the 375 px wide screen scaled to the window, and stretched to its height.
const soloBox = ref({ scale: 1, width: 375, height: 790 })
function fit() {
  const k = Math.min(window.innerWidth / 375, window.innerHeight / 790)
  soloBox.value = { scale: k, width: window.innerWidth / k, height: window.innerHeight / k }
  const room = window.innerHeight - (window.innerWidth < 900 ? 300 : 170)
  scale.value = Math.max(0.45, Math.min(1.15, room / 814))
}

const intro = computed(() => scene.value.id === 'intro')
const outro = computed(() => scene.value.id === 'outro')
const phoneStyle = computed(() => {
  if (intro.value) {
    const k = span(local.value, 1000, 800)
    return { opacity: k, transform: `translateY(${(1 - k) * 60}px) scale(${scale.value})` }
  }
  if (outro.value) {
    const k = span(local.value, 0, 500)
    return { opacity: 1 - 0.85 * k, transform: `scale(${scale.value * (1 - 0.06 * k)})` }
  }
  return { transform: `scale(${scale.value})` }
})
const clock = computed(() => {
  const s = Math.floor(t.value / 1000)
  return `0:${String(s).padStart(2, '0')} / 0:${String(Math.round(TOTAL / 1000)).padStart(2, '0')}`
})

function onKey(event: KeyboardEvent) {
  if (event.metaKey || event.ctrlKey || event.altKey) return
  const key = event.key.toLowerCase()
  if (key === ' ') toggle()
  else if (key === 'arrowright') jump(1)
  else if (key === 'arrowleft') jump(-1)
  else if (key === 'r') restart()
  else if (key === 'l') lang.value = lang.value === 'ar' ? 'en' : 'ar'
  else if (key === 'f') {
    if (document.fullscreenElement) document.exitFullscreen()
    else document.documentElement.requestFullscreen?.()
  } else return
  event.preventDefault()
}
function seekBar(event: MouseEvent) {
  const bar = event.currentTarget as HTMLElement
  const box = bar.getBoundingClientRect()
  const x = (event.clientX - box.left) / box.width
  seek((getComputedStyle(bar).direction === 'rtl' ? 1 - x : x) * TOTAL)
}

onMounted(() => {
  // ?t=12000 starts at 12 s; ?paused holds the first frame (for a slide that should not start by itself).
  const start = Number(query.get('t'))
  if (start > 0) seek(start)
  if (query.has('paused')) playing.value = false
  // ?capture: frame-by-frame video export (scratch tooling seeks with window.__kpSeek); real-time CSS
  // transitions are switched off so every frame depends only on the timeline.
  if (query.has('capture')) {
    playing.value = false
    capture.value = true
    ;(window as unknown as { __kpSeek: (ms: number) => void }).__kpSeek = (ms: number) => seek(ms)
  }
  fit()
  window.addEventListener('resize', fit)
  window.addEventListener('keydown', onKey)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', fit)
  window.removeEventListener('keydown', onKey)
})
</script>

<template>
  <div v-if="solo" class="solo" :class="{ capture, light }" @click="toggle">
    <div class="solo-screen" :style="{ width: `${soloBox.width}px`, height: `${soloBox.height}px`, transform: `scale(${soloBox.scale})` }">
      <PhoneScreen :id="scene.id" :local="local" :ar="ar" :light="light" solo />
    </div>
  </div>
  <div v-else class="show" :class="{ capture }">
    <header class="bar">
      <span class="brand"><span class="mark">KP</span>KARTOSHKA <span class="dim">· {{ tr('PRODUCT TOUR', 'جولة في المنتج') }}</span></span>
      <span class="onair" :class="{ off: !playing && !capture }"><i />{{ playing || capture ? tr('Playing', 'قيد العرض') : tr('Paused', 'متوقف') }}</span>
      <span class="demo">{{ tr('SAMPLE DATA', 'بيانات تجريبية') }}</span>
      <span class="spacer" />
      <span class="clock">{{ clock }}</span>
      <button class="ghost" @click="lang = lang === 'ar' ? 'en' : 'ar'">{{ lang === 'ar' ? 'EN' : 'عربي' }}</button>
      <button class="ghost" :aria-label="playing ? tr('Pause', 'إيقاف مؤقت') : tr('Play', 'تشغيل')" @click="toggle">
        <svg viewBox="0 0 16 16" aria-hidden="true"><path :d="playing ? 'M5 3v10M11 3v10' : 'M5 3l8 5-8 5z'" /></svg>
      </button>
    </header>

    <div class="stage">
      <div class="phone-slot" :style="{ width: `${399 * scale}px`, height: `${814 * scale}px` }">
        <div class="phone" :style="phoneStyle">
          <div class="screen">
            <PhoneScreen :id="scene.id" :local="local" :ar="ar" :light="light" />
            <span class="notch" />
          </div>
        </div>
      </div>

      <ol class="chapters" :style="{ opacity: intro ? span(local, 1200, 500) : outro ? 1 - span(local, 0, 300) : 1 }">
        <li v-for="(c, i) in CHAPTERS" :key="c.id" :class="{ now: scene.id === c.id, done: t >= sceneOf(c.id).end }" @click="seek(sceneOf(c.id).start)">
          <span class="num">{{ i + 1 }}</span>
          <span class="txt">
            <b>{{ tr(c.en, c.ar) }}</b>
            <span class="body">{{ tr(c.bodyEn, c.bodyAr) }}</span>
            <span class="pbar"><i :style="{ transform: `scaleX(${progressOf(c.id)})` }" /></span>
          </span>
        </li>
      </ol>

      <!-- Opening and closing titles over the stage -->
      <div v-if="intro" class="title" :style="{ opacity: 1 - span(local, 1150, 500) }">
        <span class="logo" :style="{ transform: `scale(${0.5 + 0.5 * span(local, 0, 600)})`, opacity: span(local, 0, 300) }">
          <svg viewBox="0 0 24 24"><path d="M12 2.5 4 5.5v6c0 4.7 3.4 9 8 10 4.6-1 8-5.3 8-10v-6l-8-3z" /><path d="m8.5 12 2.5 2.5 4.5-5" /></svg>
        </span>
        <h1 :style="{ opacity: span(local, 250, 400) }">{{ tr('Kartoshka Gatekeeper', 'الحارس من كارتوشكا') }}</h1>
        <p :style="{ opacity: span(local, 450, 400) }">{{ tr('Scam links stopped before residents pay', 'نوقف روابط الاحتيال قبل أن يدفع السكان') }}</p>
      </div>
      <div v-if="outro" class="title end" :style="{ opacity: span(local, 150, 450) }">
        <span class="logo"><svg viewBox="0 0 24 24"><path d="M12 2.5 4 5.5v6c0 4.7 3.4 9 8 10 4.6-1 8-5.3 8-10v-6l-8-3z" /><path d="m8.5 12 2.5 2.5 4.5-5" /></svg></span>
        <h1>{{ tr('Kartoshka Gatekeeper', 'الحارس من كارتوشكا') }}</h1>
        <p class="pills">
          <span v-for="([en, a], i) in ([['Block', 'احجب'], ['Check', 'افحص'], ['Report', 'أبلغ'], ['Track', 'تابع'], ['Radar', 'الرادار']] as const)" :key="en"
                :style="{ opacity: span(local, 300 + i * 90, 300), transform: `translateY(${(1 - span(local, 300 + i * 90, 300)) * 10}px)` }">{{ tr(en, a) }}</span>
        </p>
      </div>
    </div>

    <footer class="foot">
      <div class="timeline" role="slider" :aria-valuenow="Math.round(t / 1000)" :aria-valuemax="Math.round(TOTAL / 1000)" @click="seekBar">
        <span v-for="s in SCENES" :key="s.id" class="seg" :style="{ flexGrow: s.end - s.start }">
          <i :style="{ transform: `scaleX(${Math.min(1, Math.max(0, (t - s.start) / (s.end - s.start)))})` }" />
        </span>
      </div>
      <p class="keys">{{ tr('Space pause · ← → scene · R restart · L language · F full screen', 'مسافة إيقاف · ← → مشهد · R إعادة · L اللغة · F ملء الشاشة') }}</p>
    </footer>
  </div>
</template>

<style scoped>
.show {
  --ink: #0b1320; --panel: #111a2b; --line: #1e2a40; --text: #e8edf5; --muted: #93a0b5; --gold: #d7b14e; --block: #ff9483;
  position: fixed; inset: 0; display: grid; grid-template-rows: auto 1fr auto; color: var(--text); overflow: hidden; user-select: none;
  background:
    radial-gradient(55% 45% at 50% -5%, rgb(215 177 78 / 0.16), transparent 70%),
    radial-gradient(40% 40% at 85% 100%, rgb(255 148 131 / 0.07), transparent 70%),
    linear-gradient(rgb(232 237 245 / 0.025) 1px, transparent 1px) 0 0 / 100% 32px,
    var(--ink);
}
.bar { display: flex; align-items: center; gap: 1rem; padding: 0.8rem 1.5rem; border-bottom: 1px solid var(--line); background: rgb(17 26 43 / 0.7); backdrop-filter: blur(8px); }
.brand { display: inline-flex; align-items: center; gap: 0.55rem; font-weight: 800; letter-spacing: 0.14em; font-size: 0.9rem; }
.mark { display: inline-grid; place-items: center; width: 30px; height: 30px; border-radius: 7px; background: var(--gold); color: #151925; font-size: 11px; letter-spacing: 0.04em; }
.dim { color: var(--muted); font-weight: 600; }
.onair { display: inline-flex; align-items: center; gap: 0.4rem; padding: 0.15rem 0.65rem; border-radius: 999px; font-size: 0.72rem; font-weight: 800; letter-spacing: 0.12em;
  text-transform: uppercase; color: var(--block); border: 1px solid rgb(255 148 131 / 0.5); background: rgb(255 148 131 / 0.1); }
.onair i { width: 0.5rem; height: 0.5rem; border-radius: 50%; background: var(--block); box-shadow: 0 0 8px var(--block); animation: blink 1.2s infinite; }
.onair.off { color: var(--muted); border-color: var(--line); background: transparent; }
.onair.off i { background: var(--muted); box-shadow: none; animation: none; }
@keyframes blink { 50% { opacity: 0.3; } }
.demo { font-size: 0.68rem; font-weight: 800; letter-spacing: 0.12em; padding: 0.15rem 0.5rem; border-radius: 4px; color: var(--gold); border: 1px solid rgb(215 177 78 / 0.45); }
.spacer { flex: 1; }
.clock { font-family: ui-monospace, Menlo, monospace; color: var(--muted); font-variant-numeric: tabular-nums; direction: ltr; }
.ghost { min-height: 2.2rem; padding: 0 0.8rem; background: transparent; color: var(--muted); border: 1px solid var(--line); border-radius: 8px; font-weight: 700; }
.ghost svg { width: 16px; height: 16px; fill: currentColor; stroke: currentColor; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }

.stage { position: relative; display: flex; align-items: center; justify-content: center; gap: clamp(2rem, 6vw, 6rem); padding: 1rem 2rem; min-height: 0; }
.phone-slot { position: relative; flex: none; }
.phone { position: absolute; top: 0; left: 0; width: 399px; height: 814px; transform-origin: top left; padding: 12px; border-radius: 54px; background: #05080f;
  box-shadow: 0 0 0 2px #2a3346, 0 40px 90px rgb(0 0 0 / 0.55), 0 0 120px -20px rgb(215 177 78 / 0.25); }
.screen { position: relative; width: 375px; height: 790px; border-radius: 42px; overflow: hidden; background: #0b1320; }
.notch { position: absolute; top: 9px; left: 50%; width: 92px; height: 24px; margin-left: -46px; border-radius: 999px; background: #05080f; z-index: 50; }
@keyframes fade { from { opacity: 0; } }

.chapters { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.6rem; width: min(30rem, 42vw); }
.chapters li { display: flex; gap: 1rem; padding: 0.9rem 1.1rem; border-radius: 14px; border: 1px solid transparent; cursor: pointer; opacity: 0.42;
  transition: opacity 350ms, background 350ms, border-color 350ms, transform 350ms cubic-bezier(0.22, 1, 0.36, 1); }
.chapters li.done { opacity: 0.6; }
.chapters li.now { opacity: 1; background: rgb(17 26 43 / 0.85); border-color: rgb(215 177 78 / 0.4); transform: translateX(6px); box-shadow: 0 10px 40px -12px rgb(0 0 0 / 0.6); }
[dir='rtl'] .chapters li.now { transform: translateX(-6px); }
.num { display: grid; place-items: center; flex: none; width: 2.2rem; height: 2.2rem; border-radius: 50%; border: 1.5px solid var(--line); font-weight: 800; color: var(--muted); }
.chapters li.now .num { background: var(--gold); border-color: var(--gold); color: #151925; }
.chapters li.done .num { border-color: var(--gold); color: var(--gold); }
.txt { display: grid; gap: 0.3rem; min-width: 0; flex: 1; }
.txt b { font-size: 1.15rem; line-height: 1.25; }
.body { display: none; color: var(--muted); font-size: 0.95rem; line-height: 1.45; }
.chapters li.now .body { display: block; animation: fade 300ms ease both; }
.pbar { display: none; height: 3px; border-radius: 3px; background: var(--line); overflow: hidden; margin-top: 0.3rem; }
.chapters li.now .pbar { display: block; }
.pbar i { display: block; height: 100%; background: var(--gold); transform-origin: left; }
[dir='rtl'] .pbar i { transform-origin: right; }

.title { position: absolute; inset: 0; display: grid; place-content: center; justify-items: center; gap: 0.6rem; text-align: center; pointer-events: none; z-index: 5; }
.title.end { background: radial-gradient(50% 50% at 50% 50%, rgb(11 19 32 / 0.92), rgb(11 19 32 / 0.6)); }
.logo { display: grid; place-items: center; width: 6.5rem; height: 6.5rem; border-radius: 50%; background: rgb(215 177 78 / 0.12); box-shadow: 0 0 80px -10px rgb(215 177 78 / 0.6); }
.logo svg { width: 3.6rem; height: 3.6rem; fill: var(--gold); stroke: #151925; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
.title h1 { margin: 0.6rem 0 0; font-size: clamp(2rem, 4.5vw, 3.4rem); letter-spacing: -0.01em; }
.title p { margin: 0; color: var(--muted); font-size: clamp(1rem, 1.8vw, 1.35rem); }
.pills { display: flex; gap: 0.6rem; flex-wrap: wrap; justify-content: center; margin-top: 0.6rem !important; }
.pills span { padding: 0.35rem 1rem; border-radius: 999px; border: 1px solid rgb(215 177 78 / 0.45); color: var(--gold); font-weight: 700; }

.foot { padding: 0.6rem 1.5rem 0.9rem; display: grid; gap: 0.45rem; }
.timeline { display: flex; gap: 4px; height: 14px; align-items: center; cursor: pointer; }
.seg { display: block; height: 4px; border-radius: 4px; background: var(--line); overflow: hidden; flex-basis: 0; }
.seg i { display: block; height: 100%; background: var(--gold); transform-origin: left; }
[dir='rtl'] .seg i { transform-origin: right; }
.keys { margin: 0; text-align: center; color: var(--muted); font-size: 0.78rem; }

.solo { position: fixed; inset: 0; overflow: hidden; background: #0b1320; cursor: pointer; }
.solo.light { background: #f5f6f8; }
.solo-screen { position: absolute; top: 0; left: 0; transform-origin: top left; overflow: hidden; }
.solo.capture :deep(*), .show.capture :deep(*), .show.capture * { transition: none !important; animation: none !important; }
.show.capture .chapters li.now .body { display: block; }
.show.capture .ghost, .show.capture .keys { display: none; }

@media (max-width: 900px) {
  .stage { flex-direction: column; gap: 1rem; justify-content: flex-start; padding-top: 1rem; }
  .chapters { width: 100%; max-width: 30rem; }
  .chapters li:not(.now) { display: none; }
  .bar { flex-wrap: wrap; gap: 0.6rem; padding: 0.6rem 1rem; }
  .clock, .demo { display: none; }
}
</style>
