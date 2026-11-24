<script setup lang="ts">
// A finger tap at `when` (scene ms), centred on its positioned parent: the ring closes in for 350 ms,
// presses, then fades out as a ripple. Invisible outside that window.
import { computed } from 'vue'
import { clamp } from './timeline'

const props = defineProps<{ at: number; when: number }>()
const style = computed(() => {
  const d = props.at - props.when
  if (d < -350 || d > 450) return { display: 'none' }
  if (d < 0) {
    const k = clamp(1 + d / 350)
    return { left: '50%', top: '50%', opacity: k, transform: `scale(${1.7 - 0.7 * k})` }
  }
  const k = clamp(d / 450)
  return { left: '50%', top: '50%', opacity: 1 - k, transform: `scale(${0.85 + 0.9 * k})`, boxShadow: `0 0 0 ${k * 18}px rgb(255 255 255 / ${0.35 * (1 - k)})` }
})
</script>

<template>
  <span class="tap" :style="style" aria-hidden="true" />
</template>
