import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { demoRunning, findTarget, startDemo, stopDemo, type DemoStep } from './demo'
import { officer, signOut } from './session'

function button(id: string, onClick: () => void): HTMLButtonElement {
  const el = document.createElement('button')
  el.id = id
  el.addEventListener('click', onClick)
  el.getBoundingClientRect = () => ({ left: 10, top: 10, right: 60, bottom: 30, width: 50, height: 20, x: 10, y: 10, toJSON: () => ({}) })
  document.body.append(el)
  return el
}

function router() {
  return createRouter({ history: createMemoryHistory(), routes: [{ path: '/:any(.*)', component: { template: '<div />' } }] })
}

describe('demo mode', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    document.body.innerHTML = ''
    signOut()
  })
  afterEach(() => {
    stopDemo()
    vi.useRealTimers()
  })

  it('finds nothing for a missing or zero-size element', async () => {
    const hidden = document.createElement('div')
    hidden.id = 'hidden'
    document.body.append(hidden)
    const found = findTarget('#hidden', 300)
    await vi.advanceTimersByTimeAsync(400)
    expect(await found).toBeNull()
  })

  it('clicks click steps, never clicks point steps, skips missing ones, then ends', async () => {
    const clicked: string[] = []
    button('nav', () => clicked.push('nav'))
    button('confirm', () => clicked.push('confirm'))
    const steps: DemoStep[] = [
      { target: '#nav', action: 'click', caption: 'demoQueue', hold: 10 },
      { target: '#missing', action: 'click', caption: 'demoFeed', hold: 10 },
      { target: '#confirm', action: 'point', caption: 'demoConfirm', hold: 10 },
    ]
    const run = startDemo(router(), steps)
    expect(demoRunning.value).toBe(true)
    expect(officer.value).not.toBeNull()
    await vi.advanceTimersByTimeAsync(20_000)
    await run
    expect(clicked).toEqual(['nav'])
    expect(demoRunning.value).toBe(false)
  })

  it('stops on Escape without clicking later steps', async () => {
    const clicked: string[] = []
    button('a', () => clicked.push('a'))
    button('b', () => clicked.push('b'))
    const run = startDemo(router(), [
      { target: '#a', action: 'click', caption: 'demoQueue', hold: 5000 },
      { target: '#b', action: 'click', caption: 'demoFeed', hold: 10 },
    ])
    await vi.advanceTimersByTimeAsync(2000)
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await vi.advanceTimersByTimeAsync(20_000)
    await run
    expect(clicked).toEqual(['a'])
    expect(demoRunning.value).toBe(false)
  })
})

describe('demo sample data', () => {
  afterEach(() => {
    demoRunning.value = false
  })

  it('leaves data alone when the demo is not running', async () => {
    const { demoFill } = await import('./demoData')
    const empty = { packs: [] }
    expect(demoFill('/v1/admin/takedowns', empty)).toBe(empty)
  })

  it('fills only empty lists while the demo runs, and real data wins', async () => {
    const { demoFill } = await import('./demoData')
    demoRunning.value = true
    expect((demoFill('/v1/admin/takedowns', { packs: [] }) as { packs: unknown[] }).packs.length).toBeGreaterThan(0)
    expect((demoFill('/v1/admin/audit?limit=200', { entries: [] }) as { entries: unknown[] }).entries.length).toBeGreaterThan(0)
    const real = { entries: [{ id: 1 }] }
    expect(demoFill('/v1/admin/audit?limit=200', real)).toBe(real)
  })
})

describe('demo fallback', () => {
  it('has a sample for slow pages and none for the rest', async () => {
    const { demoFallback } = await import('./demoData')
    expect(demoFallback('/v1/admin/evidence/verify')).toMatchObject({ intact: true })
    expect(demoFallback('/v1/admin/helplines')).toHaveProperty('numbers')
    expect(demoFallback('/v1/admin/cases/example.com')).toBeNull()
  })
})
