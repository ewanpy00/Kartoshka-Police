import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import type { CaseDetail } from '../types'
import CaseCard from './CaseCard.vue'

const hostile = '<img src=x onerror=alert(1)>'

const detail: CaseDetail = {
  domain: 'tamm-pay.xyz',
  state: 'open',
  score: 91,
  verdict: 'block',
  brand: null,
  sources: ['hunter'],
  reports: 0,
  hits: 1,
  first_seen: '2026-11-24T10:00:00Z',
  last_seen: '2026-11-24T10:00:00Z',
  evidence_id: null,
  campaign_id: null,
  rank: 1,
  url: 'https://tamm-pay.xyz/',
  final_url: null,
  title: hostile,
  reasons: [],
  infrastructure: {},
  location: { hosted_in: null, registered_through: null, network_owner: null, behind_proxy: true },
  lead_time: { gsb: { state: 'ahead', at_least_hours: 6 } },
  report_notes: [{ id: 1, note: hostile, created_at: '2026-11-24T10:00:00Z' }],
  checks: [],
  reviews: [],
  has_screenshot: false,
}

vi.mock('../api', () => ({
  apiJson: vi.fn(async () => detail),
  postJson: vi.fn(),
  download: vi.fn(),
  fetchBlob: vi.fn(),
}))

describe('CaseCard', () => {
  it('shows a hostile title and note as text, never as markup', async () => {
    const wrapper = mount(CaseCard, { props: { domain: 'tamm-pay.xyz' }, global: { stubs: { RouterLink: true } } })
    await flushPromises()
    expect(wrapper.find('h2').text()).toBe(hostile)
    expect(wrapper.find('q').text()).toBe(hostile)
    expect(wrapper.find('img').exists()).toBe(false)
  })

  it('defangs the domain, hides the country behind a proxy and shows lead time', async () => {
    const wrapper = mount(CaseCard, { props: { domain: 'tamm-pay.xyz' }, global: { stubs: { RouterLink: true } } })
    await flushPromises()
    expect(wrapper.text()).toContain('tamm-pay[.]xyz')
    expect(wrapper.text()).toContain('behind a proxy, true host unknown')
    expect(wrapper.text()).toContain('ahead of Google Safe Browsing by at least 6 hours')
    expect(wrapper.find('a').exists()).toBe(false)
  })

  it('disables confirm and reject while there is no evidence', async () => {
    const wrapper = mount(CaseCard, { props: { domain: 'tamm-pay.xyz' }, global: { stubs: { RouterLink: true } } })
    await flushPromises()
    expect(wrapper.find('button:not(.secondary)').attributes('disabled')).toBeDefined()
    expect(wrapper.find('button.danger').attributes('disabled')).toBeDefined()
  })
})
