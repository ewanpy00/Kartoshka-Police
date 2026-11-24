import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { apiJson } from '../api'
import type { CaseDetail, Stats } from '../types'
import ImpactView from './ImpactView.vue'

vi.mock('../api', () => ({
  apiJson: vi.fn(),
  postJson: vi.fn(),
  errorText: (e: unknown) => (e instanceof Error ? e.message : String(e)),
  ApiError: class extends Error {},
}))

const hostile = '<img src=x onerror=alert(1)>.evil.example'

function stats(over: Partial<Stats['impact']> = {}): Stats {
  return {
    impact: {
      range: '24h',
      totals: {
        checks: 100,
        warn: 5,
        block: 3,
        candidates: 40,
        candidates_by_source: {},
        reports: 2,
        confirmed: 4,
        rejected: 1,
        blocked_hits: {},
        blocklist_size: 9,
        taken_down: 1,
      },
      series: [
        { bucket: '2026-11-24T08:00:00Z', checks: 3, candidates: 2, confirmed: 1 },
        { bucket: '2026-11-24T09:00:00Z', checks: 0, candidates: 1, confirmed: 0 },
      ],
      lead_domains: [],
      ...over,
    },
    quality: {} as Stats['quality'],
  }
}

function lead(gsb: string, vt: string, hours = 10): CaseDetail {
  const side = (state: string) => ({ state, at_least_hours: state === 'not_polled' ? null : hours })
  return { lead_time: { gsb: side(gsb), vt: side(vt) } } as unknown as CaseDetail
}

function domainRow(domain: string) {
  return { domain, seen: '2026-11-23T10:00:00Z', confirmed: '2026-11-23T12:00:00Z', hours_to_confirm: 2 }
}

async function render(data: Stats, cases: Record<string, CaseDetail> = {}) {
  vi.mocked(apiJson).mockImplementation(async (path: string) => {
    if (path.startsWith('/v1/admin/stats')) return data
    const domain = decodeURIComponent(path.split('/').pop() ?? '')
    if (cases[domain]) return cases[domain]
    throw new Error('missing')
  })
  const wrapper = mount(ImpactView, { global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } } })
  await flushPromises()
  return wrapper
}

describe('ImpactView', () => {
  beforeEach(() => {
    vi.mocked(apiJson).mockReset()
  })

  it('does not show a domain whose lookups were never polled', async () => {
    const wrapper = await render(stats({ lead_domains: [domainRow('never.example'), domainRow('real.example')] }), {
      'never.example': lead('not_polled', 'not_polled'),
      'real.example': lead('ahead', 'not_polled'),
    })
    const rows = wrapper.findAll('tbody tr').map((r) => r.text())
    expect(rows.some((r) => r.includes('never[.]example'))).toBe(false)
    expect(rows.some((r) => r.includes('real[.]example'))).toBe(true)
  })

  it('reads the median of the shown rows as at least N h over K cases', async () => {
    const wrapper = await render(
      stats({ lead_domains: [domainRow('a.example'), domainRow('b.example'), domainRow('c.example')] }),
      {
        'a.example': lead('ahead', 'not_polled', 10),
        'b.example': lead('hit', 'not_polled', 20),
        'c.example': lead('not_polled', 'not_polled'),
      },
    )
    expect(wrapper.text()).toContain('Median lead: at least 15 h, 2 cases')
  })

  it('shows the lead empty state and no median when nothing qualifies', async () => {
    const wrapper = await render(stats({ lead_domains: [domainRow('a.example')] }), {
      'a.example': lead('not_polled', 'not_polled'),
    })
    expect(wrapper.text()).toContain('No confirmed case has a completed')
    expect(wrapper.text()).not.toContain('Median lead')
  })

  it('shows the empty state and no chart when every value is zero', async () => {
    const wrapper = await render(
      stats({ series: [{ bucket: '2026-11-24T08:00:00Z', checks: 0, candidates: 0, confirmed: 0 }] }),
    )
    expect(wrapper.text()).toContain('No activity in this period.')
    expect(wrapper.find('svg').exists()).toBe(false)
  })

  it('draws the chart when there is volume', async () => {
    const wrapper = await render(stats())
    expect(wrapper.find('svg[role="img"]').exists()).toBe(true)
  })

  it('renders a hostile domain as text', async () => {
    const wrapper = await render(stats({ lead_domains: [domainRow(hostile)] }), { [hostile]: lead('ahead', 'ahead') })
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.text()).toContain('[.]evil[.]example')
    expect(wrapper.find('a[href^="http"]').exists()).toBe(false)
    expect(wrapper.find('tbody td.mono').exists()).toBe(true)
  })
})
