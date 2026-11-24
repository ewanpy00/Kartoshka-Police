import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { apiJson } from '../api'
import type { WatchRow } from '../types'
import WatchlistPanel from './WatchlistPanel.vue'

vi.mock('../api', () => ({
  apiJson: vi.fn(),
  errorText: (e: unknown) => String(e),
}))

const hostile = '<img src=x onerror=alert(1)>'
const future = '2099-01-01T00:00:00Z'

function row(over: Partial<WatchRow>): WatchRow {
  return { domain: 'a.example', reason: 'r', brand: null, last_status: 'parked', last_checked_at: null, checks_done: 2, next_check_at: future, expires_at: null, ...over }
}

function serve(rows: WatchRow[], asks: Record<string, string[]> = {}) {
  vi.mocked(apiJson).mockImplementation(async (path: string) => {
    if (path === '/v1/admin/watchlist') return { total: rows.length, rows }
    return { asks_for: asks[decodeURIComponent(path.split('/').pop() ?? '')] ?? [] }
  })
}

async function render(rows: WatchRow[], asks: Record<string, string[]> = {}, woke: string[] = []) {
  serve(rows, asks)
  const wrapper = mount(WatchlistPanel, { props: { woke }, global: { stubs: { RouterLink: true } } })
  await flushPromises()
  return wrapper
}

describe('WatchlistPanel', () => {
  beforeEach(() => {
    vi.mocked(apiJson).mockReset()
  })

  it('flags a live row that asks for credentials and sorts it first', async () => {
    const w = await render(
      [row({ domain: 'early.example', next_check_at: '2098-01-01T00:00:00Z' }), row({ domain: 'live.example', last_status: 'live' })],
      { 'live.example': ['password'] },
    )
    const rows = w.findAll('.q-row')
    expect(rows[0].attributes('data-domain')).toBe('live.example')
    expect(rows[0].find('.badge.block').exists()).toBe(true)
    expect(w.findAll('.badge')).toHaveLength(1)
  })

  it('shows no badge for a live row with no asks, and only looks up live rows', async () => {
    const w = await render([row({ domain: 'live.example', last_status: 'live' }), row({ domain: 'p.example' }), row({ domain: 'u.example', last_status: 'unreachable' })])
    expect(w.find('.badge').exists()).toBe(false)
    const cases = vi.mocked(apiJson).mock.calls.filter((c) => String(c[0]).includes('/cases/'))
    expect(cases).toHaveLength(1)
  })

  it('highlights a woke domain immediately', async () => {
    const w = await render([row({ domain: 'a.example' })], {}, ['a.example'])
    expect(w.find('.badge.block').exists()).toBe(true)
  })

  it('renders hostile text inertly', async () => {
    const w = await render([row({ domain: hostile, last_status: hostile })])
    expect(w.find('img').exists()).toBe(false)
    expect(w.find('a[href]').exists()).toBe(false)
  })

  it('shows the empty state', async () => {
    const w = await render([])
    expect(w.find('.empty').exists()).toBe(true)
  })
})
