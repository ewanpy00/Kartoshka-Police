// Where the live wall gets its data. The real source is the same socket and admin routes the console uses;
// the demo source (./demo.ts) plays a scripted scenario and is always labelled as demo data on screen.
import { get, onEvent, previewUrl, type LiveEvent } from '../api'
import type { CaseDetail, QueuePage, Stats } from '../types'

export interface Totals {
  candidates: number
  threats: number
  confirmed: number
  blocklist: number
}

export interface ReplayItem {
  domain: string
  verdict: string
  score: number
  brand: string | null
  source: string
}

export interface LiveSource {
  demo: boolean
  subscribe(listener: (event: LiveEvent) => void): () => void
  caseDetail(domain: string): Promise<CaseDetail | null>
  totals(): Promise<Totals | null>
  /** Recent block-band cases to replay while nothing new arrives, so the wall is never empty. */
  replay(): Promise<ReplayItem[]>
  screenshot(detail: CaseDetail): string | null
}

export const realSource: LiveSource = {
  demo: false,
  subscribe: onEvent,
  async caseDetail(domain) {
    try {
      return await get<CaseDetail>(`/v1/admin/cases/${encodeURIComponent(domain)}`)
    } catch {
      return null
    }
  },
  async totals() {
    try {
      const stats = await get<Stats>('/v1/admin/stats', { range: '24h' })
      const t = stats.totals
      return { candidates: t.candidates, threats: t.warn + t.block, confirmed: t.confirmed, blocklist: t.blocklist_size }
    } catch {
      return null
    }
  },
  async replay() {
    try {
      const page = await get<QueuePage>('/v1/admin/queue', { band: 'block' })
      return page.cases.slice(0, 12).map((row) => ({
        domain: row.domain, verdict: row.verdict ?? row.band, score: row.score, brand: row.brand, source: row.sources[0] ?? 'queue',
      }))
    } catch {
      return []
    }
  },
  screenshot(detail) {
    const id = detail.latest?.evidence_id
    return id && detail.latest?.preview ? previewUrl(id) : null
  },
}
