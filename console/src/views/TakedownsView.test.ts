import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { apiJson, postJson } from '../api'
import type { AuditEntry, TakedownDetail, TakedownRequest, TakedownStats } from '../types'
import TakedownsView from './TakedownsView.vue'

vi.mock('../api', () => ({
  apiJson: vi.fn(),
  postJson: vi.fn(),
  download: vi.fn(),
  errorText: (e: unknown) => String(e),
  ApiError: class extends Error {},
}))
vi.mock('../session', () => ({ officerName: () => 'officer1' }))

const hostile = '<img src=x onerror=alert(1)>'

function req(over: Partial<TakedownRequest>): TakedownRequest {
  return {
    id: 'r1',
    domain: 'tamm-pay.xyz',
    campaign_id: null,
    recipient_kind: 'registrar',
    recipient: 'abuse@registrar.example',
    form: false,
    status: 'sent',
    overdue: false,
    pack_sha256: 'abc',
    generated_at: '2026-11-24T08:00:00Z',
    sent_at: '2026-11-24T09:00:00Z',
    sent_by: 'officer1',
    offline_at: null,
    offline_reason: null,
    checks_offline: 0,
    ...over,
  }
}

const stats: TakedownStats = {
  by_status: { pack_ready: 0, sent: 1, offline_pending: 1, closed: 1, reopened: 0 },
  overdue: 0,
  median_hours_to_offline: null,
  recipients: [],
  sla_hours: 48,
}

let current: TakedownDetail
let audit: AuditEntry[]

function routes(requests: TakedownRequest[]) {
  vi.mocked(apiJson).mockImplementation(async (path: string) => {
    if (path.startsWith('/v1/admin/queue')) return { cases: [] }
    if (path === '/v1/admin/takedowns') return { packs: [], requests }
    if (path === '/v1/admin/takedowns/stats') return stats
    if (path.startsWith('/v1/admin/audit')) return { entries: audit }
    return current
  })
}

async function mountPage(requests: TakedownRequest[]) {
  routes(requests)
  const wrapper = mount(TakedownsView, { global: { stubs: { RouterLink: true } } })
  await flushPromises()
  return wrapper
}

const checkButton = (w: Awaited<ReturnType<typeof mountPage>>) =>
  w.findAll('button').find((b) => b.text() === 'Check now' || b.text() === 'Check running…')!

describe('TakedownsView extras', () => {
  beforeEach(() => {
    vi.mocked(apiJson).mockReset()
    vi.mocked(postJson).mockReset()
    audit = []
    vi.useFakeTimers()
  })
  afterEach(() => vi.useRealTimers())

  it('shows the offline label only for a closed request', async () => {
    const wrapper = await mountPage([
      req({ id: 'a', status: 'offline_pending', checks_offline: 1 }),
      req({ id: 'b', status: 'closed', checks_offline: 2 }),
    ])
    const rows = wrapper.findAll('tbody tr').filter((r) => r.find('.status-chip').exists())
    expect(rows[0].text()).toContain('Verifying, 1 of 2')
    expect(rows[0].text()).not.toContain('Offline')
    expect(rows[1].text()).toContain('Offline')
  })

  it('disables Check now for pack_ready and makes no POST on mount or open', async () => {
    const r = req({ status: 'pack_ready', sent_at: null })
    current = { ...r, pack: [r] }
    const wrapper = await mountPage([r])
    await wrapper.findAll('button').find((b) => b.text() === 'Details')!.trigger('click')
    await flushPromises()
    expect(checkButton(wrapper).attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('Mark the request as sent before checking.')
    expect(postJson).not.toHaveBeenCalled()
  })

  it('disables Check now after a click and re-enables it when a poll shows a change', async () => {
    const r = req({ status: 'offline_pending', checks_offline: 0 })
    current = { ...r, pack: [r] }
    vi.mocked(postJson).mockResolvedValue({ queued: true })
    const wrapper = await mountPage([r])
    await wrapper.findAll('button').find((b) => b.text() === 'Details')!.trigger('click')
    await flushPromises()
    await checkButton(wrapper).trigger('click')
    await flushPromises()
    expect(postJson).toHaveBeenCalledWith('/v1/admin/takedowns/r1/recheck', {})
    expect(checkButton(wrapper).attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('Check queued')

    await vi.advanceTimersByTimeAsync(5000)
    await flushPromises()
    expect(checkButton(wrapper).attributes('disabled')).toBeDefined()

    current = { ...current, checks_offline: 1 }
    await vi.advanceTimersByTimeAsync(5000)
    await flushPromises()
    expect(checkButton(wrapper).attributes('disabled')).toBeUndefined()
  })

  it('renders a hostile domain as text', async () => {
    const wrapper = await mountPage([req({ domain: hostile })])
    expect(wrapper.find('img').exists()).toBe(false)
  })
})
