import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { apiJson } from './api'
import { _resetHealthForTest, refreshHealth, startHealth, useHealth } from './health'
import { HUNTER_FRESH_MS, healthLevel, healthParts } from './healthLevel'
import type { Health } from './types'
import HealthView from './views/HealthView.vue'

vi.mock('./api', () => ({
  apiJson: vi.fn(),
  postJson: vi.fn(),
  errorText: (e: unknown) => (e instanceof Error ? e.message : String(e)),
}))

const mocked = vi.mocked(apiJson)
const NOW = new Date('2026-11-24T12:00:00Z').getTime()
const FRESH = new Date(NOW - 60_000).toISOString()
const OLD = new Date(NOW - HUNTER_FRESH_MS - 60_000).toISOString()

function health(over: Partial<Health> = {}): Health {
  return {
    checked_at: '2026-11-24T12:00:00Z',
    redis_ok: true,
    deep_queue: { waiting: 0, failed: 0, workers: 2 },
    hunter: [{ source: 'ct', last: FRESH, last_24h: 5 }],
    checks: { last: FRESH, last_hour: 3, deep_running: 0, deep_stale: 0 },
    models: [{ name: 'url_model', updated_at: null, score: null }],
    evidence_records: 7,
    blocklist_version: 'v1',
    ai_key_set: true,
    budget: { ai: { used: 0, limit: null, reached: false }, deep: { used: 0, limit: null, reached: false } },
    ...over,
  }
}

beforeEach(() => {
  mocked.mockReset()
  _resetHealthForTest()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('healthLevel', () => {
  it('is ok when everything is good', () => {
    expect(healthLevel(health(), NOW)).toBe('ok')
  })

  it('is down for null health, failing Redis, and no workers', () => {
    expect(healthLevel(null, NOW)).toBe('down')
    expect(healthLevel(health({ redis_ok: false }), NOW)).toBe('down')
    expect(healthLevel(health({ deep_queue: { waiting: 0, failed: 0, workers: 0 } }), NOW)).toBe('down')
    expect(healthLevel(health({ deep_queue: null }), NOW)).toBe('down')
  })

  it('is degraded for stale deep checks, failed jobs and a missing AI key', () => {
    expect(healthLevel(health({ checks: { ...health().checks, deep_stale: 1 } }), NOW)).toBe('degraded')
    expect(healthLevel(health({ deep_queue: { waiting: 0, failed: 2, workers: 1 } }), NOW)).toBe('degraded')
    expect(healthLevel(health({ ai_key_set: false }), NOW)).toBe('degraded')
  })

  it('judges Hunter by a source within 15 minutes', () => {
    expect(healthParts(health({ hunter: [{ source: 'ct', last: OLD, last_24h: 1 }] }), NOW).hunter).toBe('degraded')
    expect(healthParts(health({ hunter: [] }), NOW).hunter).toBe('degraded')
    expect(healthParts(health(), NOW).hunter).toBe('ok')
  })
})

describe('health store', () => {
  it('marks core unreachable and drops stale figures when the request fails', async () => {
    mocked.mockResolvedValueOnce(health())
    await refreshHealth()
    expect(useHealth().health.value).not.toBeNull()
    mocked.mockRejectedValueOnce(new Error('down'))
    await refreshHealth()
    expect(useHealth().reachable.value).toBe(false)
    expect(useHealth().health.value).toBeNull()
  })

  it('starts one timer and refreshes every 30 seconds', async () => {
    vi.useFakeTimers()
    mocked.mockResolvedValue(health())
    startHealth()
    startHealth()
    expect(mocked).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(30_000)
    expect(mocked).toHaveBeenCalledTimes(2)
  })
})

describe('HealthView', () => {
  it('shows only the key state and never a secret', async () => {
    mocked.mockResolvedValue({ ...health(), api_key: 'sk-test-SECRET' })
    const w = mount(HealthView)
    await flushPromises()
    expect(w.html()).not.toContain('sk-test-SECRET')
    const rows = w.findAll('dl.kv').at(-1)!.text()
    expect(rows).toContain('Set')
    expect(rows.match(/not stated/g)).toHaveLength(2)
    w.unmount()
  })
})
