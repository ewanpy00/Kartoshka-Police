import { locale, t, type Key } from './i18n'
import type { CaseSummary } from './types'

export type TagInput = Pick<CaseSummary, 'reports' | 'sources'> & {
  campaign?: { confirmed: boolean; domains: number } | null
  page_requests?: string[] | null
  behind_proxy?: boolean | null
}

const REQUEST_CODES = ['credentials', 'otp', 'card', 'id'] as const
const SOURCES = ['hunter', 'watchlist', 'officer', 'batch', 'api', 'user_report'] as const

export function rowTag(row: TagInput): { key: Key; params?: Record<string, string | number> } | null {
  if (row.campaign?.confirmed === true && row.campaign.domains > 0) {
    return { key: 'tagCampaign', params: { n: row.campaign.domains } }
  }
  const codes = (row.page_requests ?? []).filter((c): c is (typeof REQUEST_CODES)[number] =>
    (REQUEST_CODES as readonly string[]).includes(c),
  )
  if (codes.length) {
    const sep = locale.value === 'ar' ? '، ' : ', '
    return { key: 'tagAsksFor', params: { list: codes.map((c) => t(`req_${c}`)).join(sep) } }
  }
  if (row.reports > 0) {
    return row.reports === 1 ? { key: 'tagReportOne' } : { key: 'tagReports', params: { n: row.reports } }
  }
  const sources = row.sources ?? []
  const source = SOURCES.find((s) => sources.includes(s))
  if (source) return { key: `tagSource_${source}` }
  if (sources.length) return { key: 'tagSource_other' }
  if (row.behind_proxy === true) return { key: 'tagProxy' }
  return null
}

export function rowTagText(row: TagInput): string {
  const tag = rowTag(row)
  return tag ? t(tag.key, tag.params) : ''
}
