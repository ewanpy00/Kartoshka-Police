import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import type { CampaignDetail } from '../types'
import CampaignView from './CampaignView.vue'

const campaign: CampaignDetail = {
  id: 'camp_1',
  name: 'TAMM campaign',
  brand: 'TAMM',
  status: 'open',
  first_seen: '2026-11-24T10:00:00Z',
  last_activity_at: '2026-11-24T10:00:00Z',
  active: true,
  domains: [
    { domain: 'high.example', state: 'open', score: 90, evidence_id: 'e_1', excluded: null },
    { domain: 'low.example', state: 'open', score: 40, evidence_id: 'e_2', excluded: null },
    { domain: 'gov.example', state: 'open', score: 95, evidence_id: 'e_3', excluded: 'official domain' },
    { domain: 'unscored.example', state: 'open', score: null, evidence_id: null, excluded: null },
  ],
  shared: [],
  locations: [],
}

vi.mock('../api', () => ({
  apiJson: vi.fn(async (path: string) => (path.endsWith('/graph') ? { nodes: [], edges: [] } : campaign)),
  postJson: vi.fn(),
  errorText: String,
}))

describe('CampaignView confirm-all table', () => {
  it('ticks only unexcluded rows scoring 70 or more and disables excluded rows', async () => {
    const wrapper = mount(CampaignView, {
      props: { id: 'camp_1' },
      global: { stubs: { RouterLink: true, CampaignGraph: true } },
    })
    await flushPromises()
    const boxes = wrapper.findAll('tbody input[type="checkbox"]')
    const checked = boxes.map((box) => (box.element as HTMLInputElement).checked)
    expect(checked).toEqual([true, false, false, false])
    expect(boxes[2].attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('official domain')
    expect(wrapper.text()).toContain('—')
  })
})
