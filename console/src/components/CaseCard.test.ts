import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { apiJson, postJson } from '../api'
import { setLocale } from '../i18n'
import type { CaseDetail } from '../types'
import CaseCard from './CaseCard.vue'

const hostile = '<img src=x onerror=alert(1)><b>x</b>'

const base: CaseDetail = {
  domain: 'tamm-pay.xyz',
  state: 'open',
  score: 91,
  verdict: 'block',
  brand: null,
  sources: ['hunter'],
  reports: 1,
  hits: 1,
  first_seen: '2026-11-24T10:00:00Z',
  evidence_id: null,
  campaign_id: null,
  url: 'https://tamm-pay.xyz/',
  title: hostile,
  reasons: [],
  infrastructure: {},
  location: { hosted_in: null, registered_through: null, network_owner: null, behind_proxy: true },
  lead_time: { gsb: { state: 'ahead', at_least_hours: 6 } },
  report_notes: [{ id: 1, note: hostile, created_at: '2026-11-24T10:00:00Z' }],
  reviews: [],
  has_screenshot: false,
}

let current: CaseDetail = base
let exported: unknown = { id: 'e_1', check_id: 'c', seq: 12, prev_hash: null, hash: 'abc123def', created_at: '2026-11-24T10:00:00Z' }

vi.mock('../api', () => ({
  apiJson: vi.fn(async (path: string) => {
    if (path.endsWith('.json')) {
      if (!exported) throw new Error('nope')
      return exported
    }
    return current
  }),
  postJson: vi.fn(async () => ({})),
  download: vi.fn(),
  fetchBlob: vi.fn(),
}))

async function mountCard(over: Partial<CaseDetail> = {}) {
  current = { ...base, ...over }
  const wrapper = mount(CaseCard, { props: { domain: 'tamm-pay.xyz' }, global: { stubs: { RouterLink: true } } })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.mocked(postJson).mockClear()
  exported = { id: 'e_1', check_id: 'c', seq: 12, prev_hash: null, hash: 'abc123def', created_at: '2026-11-24T10:00:00Z' }
})
afterEach(() => setLocale('en'))

describe('CaseCard', () => {
  it('shows a hostile title and note as text, never as markup', async () => {
    const w = await mountCard()
    expect(w.find('.case-page-title q').text()).toBe(hostile)
    expect(w.find('.notes q').text()).toBe(hostile)
    expect(w.find('img').exists()).toBe(false)
    expect(w.find('b').exists()).toBe(false)
  })

  it('defangs the domain and never renders an anchor', async () => {
    const w = await mountCard()
    expect(w.find('h2').text()).toBe('tamm-pay[.]xyz')
    expect(w.find('a').exists()).toBe(false)
  })

  it('disables confirm without evidence and reject until a reason is chosen', async () => {
    const w = await mountCard()
    expect(w.find('button.primary').attributes('disabled')).toBeDefined()
    expect(w.find('button.danger').attributes('disabled')).toBeDefined()
    const ev = await mountCard({ evidence_id: 'e_1' })
    expect(ev.find('button.primary').attributes('disabled')).toBeUndefined()
    expect(ev.find('button.danger').attributes('disabled')).toBeDefined()
    await ev.find('select').setValue('parked_or_empty')
    expect(ev.find('button.danger').attributes('disabled')).toBeUndefined()
  })

  it('lists every reason with weight and source, in the current language only', async () => {
    const w = await mountCard({
      reasons: [
        { code: 'a', weight: 30, en: 'English one', ar: 'عربي واحد', source: 'rdap' },
        { code: 'b', weight: 20, en: 'English two', ar: 'عربي اثنان', source: 'odd<source>' },
      ],
    })
    const rows = w.findAll('.reason-list li')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('+30')
    expect(rows[0].text()).toContain('source: registration data')
    expect(rows[1].text()).toContain('source: odd<source>')
    expect(w.text()).toContain('English one')
    expect(w.text()).not.toContain('عربي واحد')
    setLocale('ar')
    await flushPromises()
    expect(w.text()).toContain('عربي واحد')
    expect(w.text()).not.toContain('English one')
  })

  it('words all four states', async () => {
    expect((await mountCard({ state: 'open' })).find('.status-chip').text()).toBe('suspected phishing page')
    const auto = await mountCard({ state: 'auto_confirmed' })
    expect(auto.find('.status-chip.suspected').text()).toContain('auto-confirmed, awaiting officer')
    expect((await mountCard({ state: 'confirmed' })).find('.status-chip.confirmed').exists()).toBe(true)
    expect((await mountCard({ state: 'rejected' })).find('.status-chip.rejected').exists()).toBe(true)
  })

  it('shows detail.score alone, never adding reports', async () => {
    const w = await mountCard({ score: 55, reports: 7 })
    const head = w.find('.case-head').text()
    expect(w.find('.score-big').text()).toBe('55')
    expect(head).not.toContain('62')
    expect(head).not.toContain('+7')
  })

  it('calls chain entries records, never blocks', async () => {
    const w = await mountCard({ evidence_id: 'e_1' })
    expect(w.text()).toContain('record 12')
    expect(w.text()).toContain('abc123def')
    expect(w.text()).not.toMatch(/block \d+/i)
  })

  it('omits the record and hash when the export fails', async () => {
    exported = null
    const w = await mountCard({ evidence_id: 'e_1' })
    expect(w.text()).not.toContain('record 12')
    expect(w.find('.hash').exists()).toBe(false)
    expect(w.find('[role=alert]').exists()).toBe(false)
  })

  it('hides country and provider behind a proxy', async () => {
    const w = await mountCard({
      infrastructure: { ip_country: 'ZZ' } as CaseDetail['infrastructure'],
      location: { hosted_in: 'Narnia', registered_through: null, network_owner: null, behind_proxy: true },
    })
    expect(w.text()).toContain('Unknown, behind a proxy service')
    expect(w.text()).not.toContain('ZZ')
    expect(w.text()).not.toContain('Narnia')
  })

  it('shows no lead time without a real lookup', async () => {
    const polled = await mountCard({
      lead_time: { gsb: { state: 'not_polled', at_least_hours: null }, vt: { state: 'not_polled', at_least_hours: null } },
    })
    expect(polled.text()).not.toContain('Lead time')
    expect((await mountCard({ lead_time: null })).text()).not.toContain('Lead time')
  })

  it('shows ahead and hit lead lines', async () => {
    const w = await mountCard({
      lead_time: { gsb: { state: 'ahead', at_least_hours: 6 }, vt: { state: 'hit', at_least_hours: 3 } },
    })
    expect(w.text()).toContain('Lead time')
    expect(w.text()).toContain('at least 6 h ahead, not listed by Google Safe Browsing yet')
    expect(w.text()).toContain('at least 3 h before VirusTotal listed it')
    const zero = await mountCard({ lead_time: { gsb: { state: 'hit', at_least_hours: 0 } } })
    expect(zero.text()).toContain('already listed by Google Safe Browsing at first lookup')
  })

  it('renders the summary only when present', async () => {
    expect((await mountCard()).text()).not.toContain('Machine-generated')
    const w = await mountCard({ summary: { en: 'English summary', ar: 'ملخص عربي' } })
    expect(w.text()).toContain('Machine-generated')
    expect(w.text()).toContain('English summary')
    expect(w.text()).toContain('ملخص عربي')
  })

  it('arms, commits and cancels the confirm', async () => {
    const w = await mountCard({ evidence_id: 'e_1' })
    const vm = w.vm as unknown as { armConfirm(): void; commitConfirm(): boolean; cancelConfirm(): void; isArmed(): boolean }
    vm.armConfirm()
    expect(vm.isArmed()).toBe(true)
    expect(postJson).not.toHaveBeenCalled()
    expect(vm.commitConfirm()).toBe(true)
    await flushPromises()
    expect(postJson).toHaveBeenCalledWith('/v1/review/e_1', expect.objectContaining({ decision: 'confirm' }))
    vi.mocked(postJson).mockClear()
    vm.armConfirm()
    vm.cancelConfirm()
    expect(vm.commitConfirm()).toBe(false)
    expect(postJson).not.toHaveBeenCalled()
    await w.find('button.primary').trigger('click')
    expect(postJson).toHaveBeenCalledTimes(1)
  })

  it('drops the previous case before the next one loads', async () => {
    const w = await mountCard({ evidence_id: 'e_1' })
    await w.find('select').setValue('test_or_internal')
    let release: (v: CaseDetail) => void = () => {}
    vi.mocked(apiJson).mockImplementationOnce(() => new Promise((resolve) => (release = resolve as never)) as never)
    await w.setProps({ domain: 'other.example' })
    const vm = w.vm as unknown as { armConfirm(): void; commitConfirm(): boolean; isArmed(): boolean }
    // The next case is still loading: nothing of the old one may be shown or acted on.
    expect(w.find('h2').exists()).toBe(false)
    vm.armConfirm()
    expect(vm.isArmed()).toBe(false)
    expect(vm.commitConfirm()).toBe(false)
    expect(postJson).not.toHaveBeenCalled()
    release({ ...base, domain: 'other.example', evidence_id: 'e_2' })
    await flushPromises()
    expect(w.find('h2').text()).toBe('other[.]example')
    expect((w.find('select').element as HTMLSelectElement).value).toBe('')
    expect(w.find('button.danger').attributes('disabled')).toBeDefined()
  })

  it('posts a confirm once on a double click and never for a confirmed case', async () => {
    const w = await mountCard({ evidence_id: 'e_1' })
    const button = w.find('button.primary')
    await button.trigger('click')
    await button.trigger('click')
    await flushPromises()
    expect(postJson).toHaveBeenCalledTimes(1)
    const done = await mountCard({ evidence_id: 'e_1', state: 'confirmed' })
    expect(done.find('button.primary').attributes('disabled')).toBeDefined()
  })

  it('does not arm without evidence', async () => {
    const w = await mountCard()
    const vm = w.vm as unknown as { armConfirm(): void; isArmed(): boolean }
    vm.armConfirm()
    expect(vm.isArmed()).toBe(false)
  })

  it('shows translated sources under Found via', async () => {
    const w = await mountCard({ sources: ['hunter', 'user_report', 'weird<x>'] })
    expect(w.text()).toContain('Found via')
    expect(w.text()).toContain('Hunter, User report, weird<x>')
  })
})

void apiJson
