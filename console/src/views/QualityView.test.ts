import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { apiJson } from '../api'
import type { AuditEntry, QualityStats, UrlModel } from '../types'
import QualityView from './QualityView.vue'

vi.mock('../api', () => ({
  apiJson: vi.fn(),
  postJson: vi.fn(),
  errorText: (e: unknown) => (e instanceof Error ? e.message : String(e)),
  ApiError: class extends Error {},
}))

const hostile = '<img src=x onerror=alert(1)>'

function entry(over: Partial<AuditEntry>): AuditEntry {
  return {
    id: 1,
    actor: 'officer1',
    action: 'case.reject',
    target: 'tamm-pay.xyz',
    before: { status: 'suspected', verdict: 'block', score: 91 },
    after: null,
    reason: null,
    created_at: '2026-11-24T10:00:00Z',
    ...over,
  }
}

const model: UrlModel = {
  updated_at: null,
  train_rows: 1000,
  holdout_rows: 200,
  officer_phish: null,
  officer_benign: null,
  dataset_name: null,
  dataset_date: null,
  held_out: null,
  metrics: [{ name: 'auc', value: 0.97 }],
  top_features: [],
}

function stats(over: Partial<QualityStats> = {}) {
  const quality: QualityStats = {
    days: 30,
    reviews: 10,
    by_band: [
      { band: 'block', confirmed: 6, cleared: 2, other_reject: 0 },
      { band: 'warn', confirmed: 1, cleared: 1, other_reject: 0 },
      { band: 'allow', confirmed: 0, cleared: 0, other_reject: 0 },
    ],
    block_precision: 0.75,
    warn_confirm_rate: 0.5,
    false_blocks: 2,
    labels_for_retrain: 8,
    url_model: model,
    ...over,
  }
  return { impact: {}, quality }
}

async function render(s: ReturnType<typeof stats>, entries: AuditEntry[] = []) {
  vi.mocked(apiJson).mockImplementation(
    async (path: string) => (path.startsWith('/v1/admin/stats') ? s : { entries }) as never,
  )
  const wrapper = mount(QualityView, { global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } } })
  await flushPromises()
  return wrapper
}

describe('QualityView', () => {
  beforeEach(() => {
    vi.mocked(apiJson).mockReset()
  })

  it('lists block-then-rejected and allow-then-confirmed only', async () => {
    const wrapper = await render(stats(), [
      entry({ id: 1, target: 'a-block.example' }),
      entry({ id: 2, action: 'case.confirm', before: { verdict: 'allow', score: 12 }, target: 'b-allow.example' }),
      entry({ id: 3, before: { verdict: 'warn', score: 50 }, target: 'c-warn.example' }),
      entry({ id: 4, action: 'case.auto_confirm', before: { verdict: 'block' }, target: 'd-auto.example' }),
    ])
    const text = wrapper.text()
    expect(text).toContain('a-block[.]example')
    expect(text).toContain('b-allow[.]example')
    expect(text).not.toContain('c-warn')
    expect(text).not.toContain('d-auto')
    expect(text).toContain('4')
  })

  it('renders not stated for missing dataset facts even with a hold-out count', async () => {
    const wrapper = await render(stats())
    const kv = wrapper.findAll('dl.kv')[1].text()
    expect(kv.match(/not stated/g)?.length).toBe(4)
    expect(wrapper.text()).toContain('Measured on 200 hold-out rows')
  })

  it('shows the empty state and no metrics table without a url model', async () => {
    const wrapper = await render(stats({ url_model: null }))
    expect(wrapper.text()).toContain('No URL model has been trained.')
    expect(wrapper.text()).not.toContain('Metric')
  })

  it('hides a rate whose value is null', async () => {
    const wrapper = await render(stats({ block_precision: null }))
    expect(wrapper.text()).not.toContain('Block precision')
    expect(wrapper.text()).toContain('Warn confirmed')
  })

  it('renders a hostile audit target as text', async () => {
    const wrapper = await render(stats(), [entry({ target: hostile, reason: hostile })])
    expect(wrapper.find('img').exists()).toBe(false)
  })
})
