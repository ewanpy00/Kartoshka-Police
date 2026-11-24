import { afterEach, describe, expect, it } from 'vitest'
import { setLocale, t } from './i18n'
import { rowTag, rowTagText, type TagInput } from './rowTag'

const full: TagInput = {
  reports: 3,
  sources: ['hunter'],
  campaign: { confirmed: true, domains: 4 },
  page_requests: ['otp', 'bogus'],
  behind_proxy: true,
}

afterEach(() => setLocale('en'))

describe('rowTag', () => {
  it('follows the priority order', () => {
    expect(rowTag(full)?.key).toBe('tagCampaign')
    expect(rowTag(full)?.params).toEqual({ n: 4 })
    const a = { ...full, campaign: null }
    expect(rowTag(a)?.key).toBe('tagAsksFor')
    expect(rowTag(a)?.params).toEqual({ list: t('req_otp') })
    const b = { ...a, page_requests: [] }
    expect(rowTag(b)).toEqual({ key: 'tagReports', params: { n: 3 } })
    const c = { ...b, reports: 0 }
    expect(rowTag(c)?.key).toBe('tagSource_hunter')
    const d = { ...c, sources: [] }
    expect(rowTag(d)?.key).toBe('tagProxy')
    expect(rowTag({ ...d, behind_proxy: false })).toBeNull()
    expect(rowTagText({ reports: 0, sources: [] })).toBe('')
  })

  it('ignores an unconfirmed or empty campaign', () => {
    expect(rowTag({ ...full, campaign: { confirmed: false, domains: 4 } })?.key).toBe('tagAsksFor')
    expect(rowTag({ ...full, campaign: { confirmed: true, domains: 0 } })?.key).toBe('tagAsksFor')
  })

  it('drops unknown request codes and falls through', () => {
    expect(rowTag({ reports: 0, sources: ['api'], page_requests: ['x', 'y'] })?.key).toBe('tagSource_api')
    const r = rowTag({ reports: 0, sources: [], page_requests: ['x', 'card', 'id'] })
    expect(r?.params).toEqual({ list: `${t('req_card')}, ${t('req_id')}` })
  })

  it('maps unknown sources to other, and picks the first known one', () => {
    expect(rowTag({ reports: 0, sources: ['mystery'] })?.key).toBe('tagSource_other')
    expect(rowTag({ reports: 0, sources: ['mystery', 'api', 'hunter'] })?.key).toBe('tagSource_hunter')
  })

  it('distinguishes one report from many', () => {
    expect(rowTagText({ reports: 1, sources: [] })).toBe('1 report')
    expect(rowTagText({ reports: 5, sources: [] })).toBe('5 reports')
  })

  it('has a distinct Arabic string for every tag key', () => {
    const rows: TagInput[] = [
      full,
      { ...full, campaign: null },
      { reports: 1, sources: [] },
      { reports: 2, sources: [] },
      ...['hunter', 'watchlist', 'officer', 'batch', 'api', 'user_report', 'zzz'].map((s) => ({ reports: 0, sources: [s] })),
      { reports: 0, sources: [], behind_proxy: true },
    ]
    for (const row of rows) {
      const tag = rowTag(row)!
      setLocale('en')
      const en = t(tag.key)
      setLocale('ar')
      const ar = t(tag.key)
      expect(ar, tag.key).toBeTruthy()
      expect(ar, tag.key).not.toBe(en)
    }
    for (const code of ['credentials', 'otp', 'card', 'id'] as const) {
      setLocale('en')
      const en = t(`req_${code}`)
      setLocale('ar')
      expect(t(`req_${code}`)).not.toBe(en)
    }
  })
})
