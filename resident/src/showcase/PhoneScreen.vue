<script setup lang="ts">
// What the phone shows at a point of the tour. On the presentation stage the opening and closing titles are
// drawn around the phone; with `solo` (the phone-only video and the app's tour mode) they are drawn inside it,
// as an app splash and an end card.
import SceneCheck from './SceneCheck.vue'
import SceneLang from './SceneLang.vue'
import SceneRadar from './SceneRadar.vue'
import SceneReport from './SceneReport.vue'
import SceneSms from './SceneSms.vue'
import { span, type SceneId } from './timeline'

const props = defineProps<{ id: SceneId; local: number; ar: boolean; solo?: boolean }>()
const T = (en: string, ar: string) => (props.ar ? ar : en)
const PILLS: [string, string][] = [['Block', 'احجب'], ['Check', 'افحص'], ['Report', 'أبلغ'], ['Track', 'تابع'], ['Radar', 'الرادار']]
</script>

<template>
  <div class="ph" :dir="ar ? 'rtl' : 'ltr'">
    <div :key="id" class="fade">
      <!-- Splash (solo only) -->
      <div v-if="id === 'intro' && solo" class="splash">
        <span class="ring" :style="{ transform: `scale(${1 + (local % 1100) / 1100 * 0.45})`, opacity: 0.8 * (1 - (local % 1100) / 1100) }" />
        <span class="logo" :style="{ transform: `scale(${0.4 + 0.6 * span(local, 0, 650)})` }">
          <svg viewBox="0 0 24 24"><path d="M12 2.5 4 5.5v6c0 4.7 3.4 9 8 10 4.6-1 8-5.3 8-10v-6l-8-3z" /><path d="m8.5 12 2.5 2.5 4.5-5" /></svg>
        </span>
        <b :style="{ opacity: span(local, 300, 400), transform: `translateY(${(1 - span(local, 300, 400)) * 10}px)` }">{{ T('Gatekeeper', 'الحارس') }}</b>
        <span class="sub" :style="{ opacity: span(local, 450, 400) }">{{ T('Scam link protection', 'حماية من روابط الاحتيال') }}</span>
      </div>
      <SceneSms v-else-if="id === 'sms' || id === 'intro'" :at="id === 'intro' ? 0 : local" :ar="ar" />
      <SceneCheck v-else-if="id === 'check'" :at="local" :ar="ar" />
      <SceneReport v-else-if="id === 'report'" :at="local" :ar="ar" />
      <SceneRadar v-else-if="id === 'radar'" :at="local" :ar="ar" />
      <!-- End card (solo only) -->
      <div v-else-if="id === 'outro' && solo" class="splash end">
        <span class="logo"><svg viewBox="0 0 24 24"><path d="M12 2.5 4 5.5v6c0 4.7 3.4 9 8 10 4.6-1 8-5.3 8-10v-6l-8-3z" /><path d="m8.5 12 2.5 2.5 4.5-5" /></svg></span>
        <b>{{ T('Gatekeeper', 'الحارس') }}</b>
        <span class="sub">{{ T('by Kartoshka', 'من كارتوشكا') }}</span>
        <span class="pills">
          <i v-for="([en, a], i) in PILLS" :key="en" :style="{ opacity: span(local, 200 + i * 90, 300), transform: `translateY(${(1 - span(local, 200 + i * 90, 300)) * 10}px)` }">{{ T(en, a) }}</i>
        </span>
      </div>
      <SceneLang v-else :at="id === 'outro' ? 2800 : local" :ar="ar" />
    </div>
  </div>
</template>

<style scoped>
.fade { position: absolute; inset: 0; animation: fade 260ms ease both; }
@keyframes fade { from { opacity: 0; } }
.splash { position: absolute; inset: 0; display: grid; place-content: center; justify-items: center; gap: 8px; text-align: center; color: #fff;
  background: radial-gradient(70% 50% at 50% 42%, #232a3b, #151925 70%); }
.ring { position: absolute; top: 50%; left: 50%; width: 132px; height: 132px; margin: -112px 0 0 -66px; border-radius: 50%; border: 2px solid #d7b14e; }
.logo { display: grid; place-items: center; width: 108px; height: 108px; border-radius: 50%; background: rgb(215 177 78 / 0.12); box-shadow: 0 0 60px -6px rgb(215 177 78 / 0.55); margin-bottom: 10px; }
.logo svg { width: 60px; height: 60px; fill: #d7b14e; stroke: #151925; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
.splash b { font-size: 30px; letter-spacing: -0.01em; }
.sub { color: #b9c0cc; font-size: 15px; }
.pills { display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; max-width: 300px; margin-top: 18px; }
.pills i { font-style: normal; padding: 5px 14px; border-radius: 999px; border: 1px solid rgb(215 177 78 / 0.5); color: #d7b14e; font-weight: 700; font-size: 14px; }
</style>
