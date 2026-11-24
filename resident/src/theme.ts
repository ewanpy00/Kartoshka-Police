// Light, dark or the phone's setting (the default). Inside Gatekeeper the app passes its choice as ?theme=,
// so the pages always match the native screens around them.
import { computed, ref, watchEffect } from 'vue'

export type Theme = 'system' | 'light' | 'dark'
const KEY = 'kp.theme'

function valid(value: string | null): value is Theme {
  return value === 'system' || value === 'light' || value === 'dark'
}

function initial(): Theme {
  const fromApp = new URLSearchParams(location.search).get('theme')
  if (valid(fromApp)) return fromApp
  try {
    const saved = localStorage.getItem(KEY)
    if (valid(saved)) return saved
  } catch {
    /* ignore */
  }
  return 'system'
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
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', dark.value ? '#0b1320' : '#151925')
  try {
    localStorage.setItem(KEY, theme.value)
  } catch {
    /* private mode */
  }
})
