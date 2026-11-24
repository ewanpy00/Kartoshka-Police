// The showcase clock: one time value in ms that drives every scene, so pause, seek and loop are exact and
// each scene draws itself from "ms since my start" (no chained timeouts that drift or pile up).
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

export type SceneId = 'intro' | 'sms' | 'check' | 'report' | 'radar' | 'lang' | 'outro'
export interface Scene { id: SceneId; start: number; end: number }

const LENGTHS: [SceneId, number][] = [
  ['intro', 1800], ['sms', 4200], ['check', 4800], ['report', 4500], ['radar', 4200], ['lang', 2800], ['outro', 1600],
]
export const SCENES: Scene[] = (() => {
  let at = 0
  return LENGTHS.map(([id, length]) => {
    const scene = { id, start: at, end: at + length }
    at += length
    return scene
  })
})()
export const TOTAL = SCENES[SCENES.length - 1].end

// --- easing and spans: every scene uses these to turn local ms into 0..1 -----------------------------

export const clamp = (x: number, a = 0, b = 1) => Math.min(b, Math.max(a, x))
export const easeOut = (x: number) => 1 - Math.pow(1 - clamp(x), 3)
export const easeInOut = (x: number) => { const v = clamp(x); return v < 0.5 ? 4 * v * v * v : 1 - Math.pow(-2 * v + 2, 3) / 2 }
/** 0 before `from`, 1 after `from + length`, eased in between. */
export const span = (at: number, from: number, length: number, ease = easeOut) => ease((at - from) / length)
/** A number rolling from 0 to `to` over the span. */
export const roll = (at: number, from: number, length: number, to: number) => Math.round(to * span(at, from, length))

export function useTimeline() {
  const t = ref(0)
  const playing = ref(true)
  let frame = 0
  let last = 0

  function tick(now: number) {
    if (last && playing.value) t.value = (t.value + Math.min(1000, now - last)) % TOTAL /* real time; only a hidden tab's gap is cut */
    last = now
    frame = requestAnimationFrame(tick)
  }

  const scene = computed(() => SCENES.find((s) => t.value >= s.start && t.value < s.end) ?? SCENES[0])
  const local = computed(() => t.value - scene.value.start)

  function seek(ms: number) {
    t.value = ((ms % TOTAL) + TOTAL) % TOTAL
  }
  function jump(step: 1 | -1) {
    const index = SCENES.indexOf(scene.value)
    // "Back" within the first second of a scene goes to the previous one, otherwise to this one's start.
    if (step < 0 && local.value > 1000) return seek(scene.value.start)
    seek(SCENES[(index + step + SCENES.length) % SCENES.length].start)
  }
  const toggle = () => { playing.value = !playing.value }
  const restart = () => { seek(0); playing.value = true }

  onMounted(() => { frame = requestAnimationFrame(tick) })
  onBeforeUnmount(() => cancelAnimationFrame(frame))
  return { t, playing, scene, local, seek, jump, toggle, restart }
}
