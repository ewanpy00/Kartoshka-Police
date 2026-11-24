import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { apiJson } from './api'
import { _resetStatsForTest, leadHours, refreshStats, startMedianLead, useStats } from './stats'

vi.mock('./api', () => ({ apiJson: vi.fn() }))

const mocked = vi.mocked(apiJson)
const NP = { state: 'not_polled' as const, at_least_hours: null }

async function settle() {
  for (let i = 0; i < 20; i++) await flushPromises()
}

beforeEach(() => {
  mocked.mockReset()
  sessionStorage.clear()
  _resetStatsForTest()
})

describe('leadHours', () => {
  it('is null when nothing was looked up', () => {
    expect(leadHours({ gsb: NP, vt: NP })).toBeNull()
    expect(leadHours(null)).toBeNull()
    expect(leadHours(undefined)).toBeNull()
  })

  it('returns the smaller value when both sides were looked up', () => {
    expect(
      leadHours({ gsb: { state: 'ahead', at_least_hours: 9 }, vt: { state: 'hit', at_least_hours: 4 } }),
    ).toBe(4)
  })

  it('keeps a hit with 0 hours', () => {
    expect(leadHours({ gsb: { state: 'hit', at_least_hours: 0 }, vt: NP })).toBe(0)
  })
})

describe('startMedianLead', () => {
  const entries = Array.from({ length: 35 }, (_, i) => ({
    id: i,
    actor: 'x',
    action: 'watchlist.add',
    target: `d${i}.example`,
    before: null,
    after: null,
    reason: null,
    created_at: '2026-11-24T10:00:00Z',
  }))

  function route(lead: (target: string) => unknown) {
    mocked.mockImplementation(async (path: string) => {
      if (path.startsWith('/v1/admin/audit')) return { entries } as never
      const target = decodeURIComponent(path.split('/').pop() ?? '')
      return { lead_time: lead(target) } as never
    })
  }

  it('fetches at most 30 cases and counts only real lookups', async () => {
    route((target) =>
      Number(target.slice(1, -8)) % 2 === 0
        ? { gsb: { state: 'ahead', at_least_hours: 10 }, vt: NP }
        : { gsb: NP, vt: NP },
    )
    startMedianLead()
    await settle()
    const caseCalls = mocked.mock.calls.filter(([p]) => String(p).startsWith('/v1/admin/cases/'))
    expect(caseCalls).toHaveLength(30)
    expect(useStats().medianLead.value).toEqual({ hours: 10, cases: 15 })
  })

  it('stays null when no case has a lookup', async () => {
    route(() => ({ gsb: NP, vt: NP }))
    startMedianLead()
    await settle()
    expect(useStats().medianLead.value).toBeNull()
  })

  it('is idempotent', async () => {
    route(() => ({ gsb: NP, vt: NP }))
    startMedianLead()
    await settle()
    const calls = mocked.mock.calls.length
    startMedianLead()
    await settle()
    expect(mocked.mock.calls.length).toBe(calls)
  })

  it('uses sessionStorage without requests', async () => {
    sessionStorage.setItem('kp.medianLead', JSON.stringify({ hours: 7, cases: 2 }))
    startMedianLead()
    await settle()
    expect(mocked).not.toHaveBeenCalled()
    expect(useStats().medianLead.value).toEqual({ hours: 7, cases: 2 })
  })

  it('leaves the ref null and does not throw when the fetch rejects', async () => {
    mocked.mockRejectedValue(new Error('down'))
    expect(() => startMedianLead()).not.toThrow()
    await settle()
    expect(useStats().medianLead.value).toBeNull()
  })
})

describe('refreshStats', () => {
  it('keeps the other two values when one request fails', async () => {
    mocked.mockImplementation(async (path: string) => {
      if (path.startsWith('/v1/admin/queue')) return { cases: [{}, {}] } as never
      if (path.startsWith('/v1/admin/audit')) throw new Error('boom')
      return { intact: true, count: 5, first_broken: null, message: '' } as never
    })
    await refreshStats()
    const s = useStats()
    expect(s.awaiting.value).toBe(2)
    expect(s.autoConfirmedToday.value).toBeNull()
    expect(s.chain.value).toEqual({ intact: true, count: 5, brokenSeq: null })
  })
})
