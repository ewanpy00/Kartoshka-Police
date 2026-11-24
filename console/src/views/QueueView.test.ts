import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { apiJson, postJson } from '../api'
import { refreshStats, startMedianLead } from '../stats'
import type { CaseSummary } from '../types'
import QueueView from './QueueView.vue'

const spies = {
  armConfirm: vi.fn(),
  commitConfirm: vi.fn(() => true),
  cancelConfirm: vi.fn(),
  isArmed: vi.fn(() => false),
  focusReject: vi.fn(),
}

vi.mock('../api', () => ({
  apiJson: vi.fn(),
  postJson: vi.fn(async () => ({})),
  errorText: (e: unknown) => String(e),
}))
vi.mock('../session', () => ({ officerName: () => 'officer-1' }))
vi.mock('../stats', () => ({
  refreshStats: vi.fn(async () => {}),
  startMedianLead: vi.fn(() => new Promise(() => {})),
  useStats: () => ({ awaiting: ref(null), autoConfirmedToday: ref(null), chain: ref(null), medianLead: ref(null) }),
}))

const CardStub = defineComponent({
  props: { domain: String },
  setup(_, { expose }) {
    expose(spies)
    return () => h('div', { class: 'card-stub' })
  },
})

function row(domain: string, over: Partial<CaseSummary> = {}): CaseSummary {
  return {
    domain,
    state: 'open',
    score: 50,
    verdict: 'warn',
    brand: null,
    sources: ['hunter'],
    reports: 0,
    hits: 1,
    first_seen: new Date(Date.now() - 5 * 60_000).toISOString(),
    evidence_id: null,
    campaign_id: null,
    ...over,
  }
}

let openRows: CaseSummary[] = []
let autoRows: CaseSummary[] = []

async function setup(path = '/queue') {
  vi.mocked(apiJson).mockImplementation(async (url: string) => ({
    cases: url.includes('auto_confirmed') ? autoRows : openRows,
  }) as never)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/queue/:domain?', component: { render: () => null } }],
  })
  await router.push(path)
  const wrapper = mount(QueueView, {
    attachTo: document.body,
    global: { plugins: [router], stubs: { CaseCard: CardStub, StatStrip: true } },
  })
  mounted.push(wrapper)
  await flushPromises()
  return { wrapper, router }
}

// Unmount even when an assertion failed, so no window keydown listener leaks into the next test.
const mounted: { unmount(): void }[] = []
afterEach(() => {
  for (const w of mounted.splice(0)) {
    try {
      w.unmount()
    } catch {
      // Already unmounted by the test.
    }
  }
})

function press(key: string, target: EventTarget = document.body) {
  target.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }))
}

beforeEach(() => {
  vi.clearAllMocks()
  spies.isArmed.mockReturnValue(false)
  openRows = [
    row('evil-bank.xyz', { score: 91, brand: 'Emirates NBD', reports: 3 }),
    row('tamm-pay.xyz', { score: 40, brand: 'TAMM' }),
    row('plain.top', { score: 10, sources: [] }),
  ]
  autoRows = [row('auto.example', { state: 'auto_confirmed', score: 95, brand: 'TAMM' })]
})

describe('QueueView', () => {
  it('renders a row with defanged domain, brand, tag, score and age', async () => {
    const { wrapper } = await setup()
    const first = wrapper.findAll('.q-row')[0]
    expect(first.find('.q-domain').text()).toBe('evil-bank[.]xyz')
    expect(first.find('.q-sub').text()).toContain('Impersonates Emirates NBD')
    expect(first.find('.q-sub').text()).toContain('3 reports')
    expect(first.find('.q-score').text()).toBe('91')
    expect(first.find('.q-score').classes()).toContain('high')
    expect(first.find('.q-age').text()).toBe('5 min')
    expect(wrapper.find('a').exists()).toBe(false)
    wrapper.unmount()
  })

  it('shows the empty state', async () => {
    openRows = []
    autoRows = []
    const { wrapper } = await setup()
    expect(wrapper.find('.empty').text()).toBe('No cases awaiting review')
    wrapper.unmount()
  })

  it('search filters rows and reports no matches', async () => {
    const { wrapper } = await setup()
    await wrapper.find('input[type="search"]').setValue('TAMM')
    expect(wrapper.findAll('.q-row').map((r) => r.find('.q-domain').text())).toEqual(['tamm-pay[.]xyz', 'auto[.]example'])
    await wrapper.find('input[type="search"]').setValue('zzzz')
    expect(wrapper.text()).toContain('No cases match this search')
    wrapper.unmount()
  })

  it('brand chip filters and shows its count; high risk chip filters', async () => {
    const { wrapper } = await setup()
    const chips = wrapper.findAll('.chip')
    const tamm = chips.find((c) => c.text().startsWith('TAMM'))!
    // Counts cover the cases awaiting review only; the auto-confirmed TAMM row is not counted.
    expect(tamm.find('.count').text()).toBe('1')
    await tamm.trigger('click')
    expect(tamm.attributes('aria-pressed')).toBe('true')
    expect(wrapper.findAll('.q-row')).toHaveLength(2)
    const high = chips.find((c) => c.text().startsWith('High risk'))!
    await high.trigger('click')
    expect(wrapper.findAll('.q-row').map((r) => r.find('.q-domain').text())).toEqual(['evil-bank[.]xyz', 'auto[.]example'])
    expect(tamm.attributes('aria-pressed')).toBe('false')
    wrapper.unmount()
  })

  it('auto-confirmed row shows Undo that posts', async () => {
    const { wrapper } = await setup()
    const dim = wrapper.find('.q-row.dim')
    expect(dim.find('.q-score').exists()).toBe(false)
    const btn = wrapper.find('button.undo-btn')
    expect(btn.text()).toBe('Undo')
    await btn.trigger('click')
    await flushPromises()
    expect(postJson).toHaveBeenCalledWith('/v1/admin/cases/auto.example/undo-auto-confirm', { reviewer: 'officer-1' })
    expect(refreshStats).toHaveBeenCalled()
    wrapper.unmount()
  })

  it('j and k move the selection', async () => {
    const { wrapper, router } = await setup()
    press('j')
    await flushPromises()
    expect(router.currentRoute.value.params.domain).toBe('evil-bank.xyz')
    press('J')
    await flushPromises()
    expect(router.currentRoute.value.params.domain).toBe('tamm-pay.xyz')
    expect(spies.cancelConfirm).toHaveBeenCalled()
    press('k')
    await flushPromises()
    expect(router.currentRoute.value.params.domain).toBe('evil-bank.xyz')
    press('k')
    await flushPromises()
    expect(router.currentRoute.value.params.domain).toBe('evil-bank.xyz')
    wrapper.unmount()
  })

  it('c arms without sending anything', async () => {
    const { wrapper } = await setup('/queue/evil-bank.xyz')
    press('c')
    expect(spies.armConfirm).toHaveBeenCalled()
    expect(postJson).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('Enter commits only while armed; Escape cancels while armed', async () => {
    const { wrapper } = await setup('/queue/evil-bank.xyz')
    press('Enter')
    press('Escape')
    expect(spies.commitConfirm).not.toHaveBeenCalled()
    expect(spies.cancelConfirm).not.toHaveBeenCalled()
    spies.isArmed.mockReturnValue(true)
    press('Enter')
    expect(spies.commitConfirm).toHaveBeenCalledTimes(1)
    press('Escape')
    expect(spies.cancelConfirm).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  it('r focuses reject', async () => {
    const { wrapper } = await setup('/queue/evil-bank.xyz')
    press('r')
    expect(spies.focusReject).toHaveBeenCalled()
    wrapper.unmount()
  })

  it('ignores shortcuts typed in the search input', async () => {
    const { wrapper } = await setup('/queue/evil-bank.xyz')
    press('c', wrapper.find('input[type="search"]').element)
    expect(spies.armConfirm).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('starts the median lead once and renders without it', async () => {
    const { wrapper } = await setup()
    expect(startMedianLead).toHaveBeenCalledTimes(1)
    expect(wrapper.findAll('.q-row').length).toBe(4)
    wrapper.unmount()
  })
})
