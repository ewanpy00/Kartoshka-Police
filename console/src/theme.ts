import { ref, type Ref } from 'vue'

export type Theme = 'light' | 'dark'

const QUERY = '(prefers-color-scheme: dark)'

function storedTheme(): Theme | null {
  try {
    const value = localStorage.getItem('theme')
    return value === 'light' || value === 'dark' ? value : null
  } catch {
    return null
  }
}

function osTheme(): Theme {
  return window.matchMedia?.(QUERY)?.matches ? 'dark' : 'light'
}

export const theme: Ref<Theme> = ref<Theme>('light')
let explicit = false
let watching = false

function apply(next: Theme): void {
  theme.value = next
  document.documentElement.dataset.theme = next
}

export function initTheme(): void {
  const saved = storedTheme()
  explicit = saved !== null
  apply(saved ?? osTheme())
  if (watching) return
  const query = window.matchMedia?.(QUERY)
  if (!query?.addEventListener) return
  watching = true
  query.addEventListener('change', (event: MediaQueryListEvent) => {
    if (!explicit && storedTheme() === null) apply(event.matches ? 'dark' : 'light')
  })
}

export function setTheme(next: Theme): void {
  explicit = true
  apply(next)
  try {
    localStorage.setItem('theme', next)
  } catch {
    // Storage may be blocked; the choice then lasts only for this page load.
  }
}

export function toggleTheme(): void {
  setTheme(theme.value === 'dark' ? 'light' : 'dark')
}
