import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

type Listener = (e: { matches: boolean }) => void

function stubMatchMedia(matches: boolean) {
  const listeners: Listener[] = []
  vi.stubGlobal('matchMedia', () => ({
    matches,
    addEventListener: (_: string, l: Listener) => listeners.push(l),
    removeEventListener: () => undefined,
  }))
  window.matchMedia = (globalThis as unknown as { matchMedia: typeof window.matchMedia }).matchMedia
  return listeners
}

async function load() {
  vi.resetModules()
  return import('./theme')
}

describe('theme', () => {
  beforeEach(() => {
    localStorage.clear()
    delete document.documentElement.dataset.theme
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    delete (window as { matchMedia?: unknown }).matchMedia
  })

  it('a stored dark wins over a light OS', async () => {
    stubMatchMedia(false)
    localStorage.setItem('theme', 'dark')
    const m = await load()
    m.initTheme()
    expect(m.theme.value).toBe('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
  })

  it('follows a dark OS and stores nothing', async () => {
    stubMatchMedia(true)
    const m = await load()
    m.initTheme()
    expect(m.theme.value).toBe('dark')
    expect(localStorage.getItem('theme')).toBeNull()
  })

  it('falls back to light without matchMedia', async () => {
    const m = await load()
    expect(() => m.initTheme()).not.toThrow()
    expect(m.theme.value).toBe('light')
  })

  it('toggle flips ref, attribute and storage', async () => {
    const m = await load()
    m.initTheme()
    m.toggleTheme()
    expect(m.theme.value).toBe('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(localStorage.getItem('theme')).toBe('dark')
    m.toggleTheme()
    expect(m.theme.value).toBe('light')
    expect(localStorage.getItem('theme')).toBe('light')
  })

  it('OS changes follow live until an explicit choice', async () => {
    const listeners = stubMatchMedia(false)
    const m = await load()
    m.initTheme()
    listeners.forEach((l) => l({ matches: true }))
    expect(m.theme.value).toBe('dark')
    m.setTheme('light')
    listeners.forEach((l) => l({ matches: true }))
    expect(m.theme.value).toBe('light')
  })
})
