// Light, dark or follow the system. The choice is a per-browser convenience, so losing it is harmless.
import { computed, ref, watchEffect } from 'vue'

export type Theme = 'system' | 'light' | 'dark'
const KEY = 'kp.console.theme'

function initial(): Theme {
  try {
    const saved = localStorage.getItem(KEY)
    return saved === 'light' || saved === 'dark' ? saved : 'system'
  } catch {
    return 'system'
  }
}

const media = typeof matchMedia === 'function' ? matchMedia('(prefers-color-scheme: dark)') : null
const systemDark = ref(media?.matches ?? false)
media?.addEventListener('change', (event) => { systemDark.value = event.matches })

export const theme = ref<Theme>(initial())
export const dark = computed(() => theme.value === 'dark' || (theme.value === 'system' && systemDark.value))

watchEffect(() => {
  const root = document.documentElement
  if (theme.value === 'system') root.removeAttribute('data-theme')
  else root.setAttribute('data-theme', theme.value)
  try {
    if (theme.value === 'system') localStorage.removeItem(KEY)
    else localStorage.setItem(KEY, theme.value)
  } catch {
    /* private mode: the choice lasts until reload */
  }
})

export function cycleTheme(): void {
  theme.value = theme.value === 'system' ? (systemDark.value ? 'light' : 'dark') : theme.value === 'dark' ? 'light' : 'dark'
}

/** A colour token as the page currently resolves it, for canvas libraries (cytoscape, chart.js) that cannot read CSS. */
export function cssVar(name: string, fallback = '#888'): string {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return value || fallback
}
