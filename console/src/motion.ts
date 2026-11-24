// Small motion helpers. Every effect collapses to its end state when the viewer asks for reduced motion.
import { onBeforeUnmount, ref, watch, type Ref } from 'vue'

const media = typeof matchMedia === 'function' ? matchMedia('(prefers-reduced-motion: reduce)') : null
export const reducedMotion = ref(media?.matches ?? false)
media?.addEventListener('change', (event) => { reducedMotion.value = event.matches })

const easeOut = (x: number) => 1 - Math.pow(1 - x, 3)

/** A number that rolls towards `target` instead of jumping (stat tiles, scores). */
export function useCountUp(target: () => number, duration = 700): Ref<number> {
  const shown = ref(0)
  let frame = 0
  watch(target, (to) => {
    cancelAnimationFrame(frame)
    const from = shown.value
    if (reducedMotion.value || from === to) {
      shown.value = to
      return
    }
    const start = performance.now()
    const step = (now: number) => {
      const progress = Math.min(1, (now - start) / duration)
      shown.value = Math.round(from + (to - from) * easeOut(progress))
      if (progress < 1) frame = requestAnimationFrame(step)
    }
    frame = requestAnimationFrame(step)
  }, { immediate: true })
  onBeforeUnmount(() => cancelAnimationFrame(frame))
  return shown
}

/** Marks keys for a short while (row flash, node pulse); the set empties itself. */
export function useFlash(ms = 1600) {
  const keys = ref(new Set<string>())
  const timers = new Map<string, number>()
  function flash(key: string) {
    window.clearTimeout(timers.get(key))
    keys.value = new Set(keys.value).add(key)
    timers.set(key, window.setTimeout(() => {
      const next = new Set(keys.value)
      next.delete(key)
      keys.value = next
      timers.delete(key)
    }, ms))
  }
  onBeforeUnmount(() => timers.forEach((timer) => window.clearTimeout(timer)))
  return { keys, flash }
}
