import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { apiJson, postJson } from '../api'
import { t } from '../i18n'
import type { CampaignDetail, EntityCard, Pivot } from '../types'
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
  shared: [{ kind: 'ip', value: '1.2.3.4', strength: 'strong', domain_count: 2 }],
  locations: [],
}

const hostile = '<img src=x onerror=alert(1)>'
const entityCard: EntityCard = {
  kind: 'ip',
  value: hostile,
  label: hostile,
  first_seen: null,
  domain_count: 1,
  hub: true,
  domains: [{ domain: hostile, status: null, strength: 'strong', excluded: true, campaign: null, score: null }],
}

vi.mock('../api', () => ({
  apiJson: vi.fn(),
  postJson: vi.fn(),
  errorText: String,
}))

beforeEach(() => {
  vi.mocked(apiJson).mockReset()
  vi.mocked(postJson).mockReset()
  vi.mocked(apiJson).mockImplementation(async (path: string) => {
    if (path.endsWith('/graph')) return { nodes: [], edges: [] }
    if (path === '/v1/admin/campaigns') return { campaigns: [{ id: 'camp_1', name: 'A' }, { id: 'camp_2', name: 'B' }] }
    if (path.startsWith('/v1/admin/entities/')) return entityCard
    return campaign
  })
})

const mountView = () =>
  mount(CampaignView, { props: { id: 'camp_1' }, global: { stubs: { RouterLink: true, CampaignGraph: true } } })

async function setReason(wrapper: ReturnType<typeof mountView>, value: string) {
  await wrapper.find('.reason-confirm input').setValue(value)
}

describe('CampaignView confirm-all table', () => {
  it('ticks only unexcluded rows scoring above 70 and disables excluded rows', async () => {
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

describe('CampaignView actions', () => {
  it('exclude needs a reason, then two activations, then posts once', async () => {
    vi.mocked(postJson).mockResolvedValue({ domain: 'high.example', domain_count: 1 })
    const wrapper = mountView()
    await flushPromises()
    await wrapper.findAll('tbody .btn.danger')[0].trigger('click')
    const action = () => wrapper.find('.reason-confirm .actions .btn')
    await setReason(wrapper, '   ')
    await action().trigger('click')
    expect(wrapper.text()).toContain(t('reasonRequired'))
    expect(postJson).not.toHaveBeenCalled()
    await setReason(wrapper, 'lookalike')
    await action().trigger('click')
    expect(action().classes()).toContain('armed')
    expect(postJson).not.toHaveBeenCalled()
    await action().trigger('click')
    await flushPromises()
    expect(postJson).toHaveBeenCalledTimes(1)
    expect(postJson).toHaveBeenCalledWith('/v1/admin/campaigns/camp_1/exclude', {
      domain: 'high.example',
      reviewer: 'Demo Officer',
      reason: 'lookalike',
    })
  })

  it('merge is unavailable without a selected campaign or a reason', async () => {
    vi.mocked(postJson).mockResolvedValue({ id: 'camp_1', merged: [] })
    const wrapper = mountView()
    await flushPromises()
    const action = () => wrapper.find('.reason-confirm .actions .btn')
    expect(action().attributes('disabled')).toBeDefined()
    expect(wrapper.findAll('select option').map((o) => o.text())).toEqual(['', 'B (camp_2)'])
    await wrapper.find('select').setValue('camp_2')
    await action().trigger('click')
    await action().trigger('click')
    expect(postJson).not.toHaveBeenCalled()
    await setReason(wrapper, 'same actor')
    await action().trigger('click')
    await action().trigger('click')
    await flushPromises()
    expect(postJson).toHaveBeenCalledTimes(1)
    expect(postJson).toHaveBeenCalledWith('/v1/admin/campaigns/merge', {
      ids: ['camp_1', 'camp_2'],
      reviewer: 'Demo Officer',
      reason: 'same actor',
    })
  })

  it('pivot posts once to the pivot path and offers no write control on leads', async () => {
    const pivot: Pivot = {
      total: 1,
      leads: [{ domain: hostile, via: [{ kind: 'ip', label: hostile, strong: true }], status: 'open', score: 80, campaign: null }],
    }
    vi.mocked(postJson).mockResolvedValue(pivot)
    const wrapper = mountView()
    await flushPromises()
    const button = wrapper.findAll('button').find((b) => b.text() === t('campPivot'))
    await button?.trigger('click')
    await flushPromises()
    expect(postJson).toHaveBeenCalledTimes(1)
    expect(postJson).toHaveBeenCalledWith('/v1/admin/campaigns/camp_1/pivot', {})
    expect(wrapper.find('table.leads').exists()).toBe(true)
    expect(wrapper.find('table.leads button').exists()).toBe(false)
    expect(wrapper.find('img').exists()).toBe(false)
  })

  it('shows why a refused site was refused and never lists it as confirmed', async () => {
    vi.mocked(postJson).mockResolvedValue({
      confirmed: ['high.example', 'gov.example'],
      skipped: [{ domain: 'gov.example', reason: 'official' }],
    })
    const wrapper = mountView()
    await flushPromises()
    await wrapper.find('.btn.primary').trigger('click')
    await flushPromises()
    expect(wrapper.find('.refused').text()).toContain(t('refusedOfficial'))
    expect(wrapper.text()).toContain(`${t('confirmedList')}: high[.]example${t('campRefusedTitle')}`)
  })

  it('renders a hostile entity value as text', async () => {
    const wrapper = mountView()
    await flushPromises()
    await wrapper.findAll('button').find((b) => b.text() === t('details'))?.trigger('click')
    await flushPromises()
    expect(wrapper.find('.entity-card').exists()).toBe(true)
    expect(wrapper.find('img').exists()).toBe(false)
  })
})
