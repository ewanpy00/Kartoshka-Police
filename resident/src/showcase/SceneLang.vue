<script setup lang="ts">
// Scene 5: Home in the other language (Arabic, right to left, when the show runs in English) in the light
// theme; then the theme switch flips it to dark with a circular reveal from the switch.
import { computed } from 'vue'
import PhoneHome from './PhoneHome.vue'
import { span } from './timeline'

const props = defineProps<{ at: number; ar: boolean }>()
const other = computed(() => !props.ar)
const DARK = 1350
const reveal = computed(() => span(props.at, DARK, 750))
</script>

<template>
  <div class="scene" :style="{ opacity: span(at, 0, 300) }">
    <div class="ph light" :dir="other ? 'rtl' : 'ltr'"><PhoneHome :ar="other" /></div>
    <div v-if="at >= DARK" class="ph" :dir="other ? 'rtl' : 'ltr'" :style="{ clipPath: `circle(${reveal * 150}% at 50% 84%)` }">
      <PhoneHome :ar="other" />
    </div>
    <div class="switches" :style="{ opacity: span(at, 200, 300), transform: `translateY(${(1 - span(at, 200, 350)) * 16}px)` }">
      <span class="seg"><i :class="{ on: !other }">EN</i><i :class="{ on: other }">عربي</i></span>
      <span class="seg"><i :class="{ on: at < DARK }">☀</i><i :class="{ on: at >= DARK }">☾</i></span>
    </div>
  </div>
</template>

<style scoped>
.scene { position: absolute; inset: 0; }
.switches { position: absolute; bottom: 92px; inset-inline: 0; z-index: 10; display: flex; justify-content: center; gap: 10px; direction: ltr; }
.seg { display: inline-flex; padding: 3px; border-radius: 999px; background: rgb(17 26 43 / 0.92); border: 1px solid rgb(255 255 255 / 0.15); box-shadow: 0 8px 24px rgb(0 0 0 / 0.35); }
.seg i { font-style: normal; min-width: 44px; padding: 5px 12px; border-radius: 999px; text-align: center; color: #b9c0cc; font-weight: 700; font-size: 13.5px; transition: background 250ms, color 250ms; }
.seg i.on { background: #d7b14e; color: #151925; }
</style>
