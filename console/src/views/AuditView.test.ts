import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { apiJson } from '../api'
import type { AuditEntry } from '../types'
import AuditView from './AuditView.vue'

vi.mock('../api', () => ({
  apiJson: vi.fn(),
  postJson: vi.fn(),
  download: vi.fn(),
  fetchBlob: vi.fn(),
  errorText: (e: unknown) => (e instanceof Error ? e.message : String(e)),
}))

const hostile = '<img src=x onerror=alert(1)>'

function entry(over: Partial<AuditEntry>): AuditEntry {
  return {
    id: 1,
    actor: 'officer1',
    action: 'case.confirm',
    target: 'tamm-pay.xyz',
    before: null,
    after: null,
    reason: null,
    created_at: '2026-11-24T10:00:00Z',
    ...over,
  }
}

async function render(entries: AuditEntry[]) {
  vi.mocked(apiJson).mockResolvedValue({ entries })
  const wrapper = mount(AuditView)
  await flushPromises()
  return wrapper
}

describe('AuditView', () => {
  beforeEach(() => vi.mocked(apiJson).mockReset())

  it('shows translated actions and defanged targets without links', async () => {
    const wrapper = await render([
      entry({ id: 2, action: 'case.reject', target: 'a-b.example.com' }),
      entry({ id: 1 }),
    ])
    expect(apiJson).toHaveBeenCalledWith('/v1/admin/audit?limit=200')
    const rows = wrapper.findAll('tbody tr')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('Case rejected')
    expect(rows[1].text()).toContain('Case confirmed')
    expect(rows[1].text()).toContain('tamm-pay[.]xyz')
    expect(rows[1].text()).not.toContain('tamm-pay.xyz')
    expect(wrapper.find('a').exists()).toBe(false)
  })

  it('shows an unknown action as its raw string', async () => {
    const wrapper = await render([entry({ action: 'mystery.thing' })])
    expect(wrapper.find('tbody').text()).toContain('mystery.thing')
  })

  it('renders a hostile reason as literal text', async () => {
    const wrapper = await render([entry({ reason: hostile })])
    expect(wrapper.find('tbody').text()).toContain(hostile)
    expect(wrapper.find('img').exists()).toBe(false)
  })

  it('shows the empty text for no entries', async () => {
    const wrapper = await render([])
    expect(wrapper.find('.empty').text()).toBe('No audit entries yet')
    expect(wrapper.find('table').exists()).toBe(false)
  })

  it('shows an error and no rows when the request fails', async () => {
    vi.mocked(apiJson).mockRejectedValueOnce(new Error('boom'))
    const wrapper = mount(AuditView)
    await flushPromises()
    expect(wrapper.find('[role="alert"]').text()).toContain('boom')
    expect(wrapper.findAll('tbody tr')).toHaveLength(0)
  })
})
