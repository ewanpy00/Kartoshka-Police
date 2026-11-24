// Sample data shown only while the demo tour runs, so pages with no real data yet still look complete.
//
// Rules: real data wins when it arrives within DEMO_WAIT_MS (a sample fills a list only when the real list is
// empty), nothing here is ever sent to core, and everything disappears when the demo stops, because the pages
// that can show samples load real data again. All recipients, phone numbers and domains are made up.
import { demoRunning } from './demo'
import type { AuditEntry, CaseDetail, CaseSummary, Helpline, Pack, Stats, TakedownRequest, TakedownStats, Verify } from './types'

function ago(minutes: number): string {
  return new Date(Date.now() - minutes * 60_000).toISOString()
}

const SAMPLE_DOMAINS = ['tamm-pay.xyz', 'uaepass-verify.top', 'adcb-secure.co', 'rta-fines-uae.online']

function samplePacks(): Pack[] {
  return [
    {
      id: 'demo_req_1',
      recipient_kind: 'Registrar',
      recipient: 'abuse@registrar.example',
      domains: ['tamm-pay.xyz', 'rta-fines-uae.online'],
      sha256: '9f2c4e81b07a5d3361c2f0e9a4b85d17c6e3a2f09b8d4c1e7a5f3b2d6c9e0a14',
      generated_at: ago(42),
      sent_at: ago(35),
      sent_by: 'Demo Officer',
    },
    {
      id: 'demo_req_3',
      recipient_kind: 'Hosting provider',
      recipient: 'abuse@hosting.example',
      domains: ['uaepass-verify.top', 'adcb-secure.co'],
      sha256: '3b7e9d02c4a1f86e5d2b90c7a3e14f6b8d05c2a9e7f31b4d6a8c0e2f5b9d7a13',
      generated_at: ago(12),
      sent_at: null,
      sent_by: null,
    },
  ]
}

function sampleRequests(): TakedownRequest[] {
  const request = (
    id: string,
    domain: string,
    pack: Pack,
    status: TakedownRequest['status'],
    extra: Partial<TakedownRequest> = {},
  ): TakedownRequest => ({
    id,
    domain,
    campaign_id: null,
    recipient_kind: pack.recipient_kind,
    recipient: pack.recipient,
    form: false,
    status,
    overdue: false,
    pack_sha256: pack.sha256,
    generated_at: pack.generated_at,
    sent_at: pack.sent_at,
    sent_by: pack.sent_by,
    offline_at: null,
    offline_reason: null,
    checks_offline: 0,
    ...extra,
  })
  const [sent, ready] = samplePacks()
  return [
    request('demo_req_1', 'tamm-pay.xyz', sent, 'closed', { offline_at: ago(8), offline_reason: 'dns_gone', checks_offline: 2 }),
    request('demo_req_2', 'rta-fines-uae.online', sent, 'offline_pending', { offline_at: ago(5), checks_offline: 1 }),
    request('demo_req_3', 'uaepass-verify.top', ready, 'pack_ready'),
    request('demo_req_4', 'adcb-secure.co', ready, 'pack_ready'),
  ]
}

function sampleTakedownStats(): TakedownStats {
  return {
    by_status: { pack_ready: 2, sent: 0, offline_pending: 1, closed: 1, reopened: 0 },
    overdue: 0,
    median_hours_to_offline: 0.5,
    recipients: [
      { kind: 'Registrar', requests: 2, closed: 1, median_hours: 0.5 },
      { kind: 'Hosting provider', requests: 2, closed: 0, median_hours: null },
    ],
    sla_hours: 48,
  }
}

function sampleAudit(): AuditEntry[] {
  const entry = (
    id: number,
    minutes: number,
    actor: string,
    action: string,
    target: string,
    reason: string | null,
    before: AuditEntry['before'] = null,
  ): AuditEntry => ({
    id,
    actor,
    action,
    target,
    before,
    after: null,
    reason,
    created_at: ago(minutes),
  })
  return [
    entry(-1, 3, 'Demo Officer', 'takedown.pack_built', 'demo_req_3', null),
    entry(-2, 9, 'Demo Officer', 'case.confirm', 'adcb-secure.co', 'Asks for card number and OTP', { verdict: 'warn', score: 66 }),
    entry(-3, 14, 'system', 'case.auto_confirm', 'uaepass-verify.top', 'Deep score over 90 with a login form', { verdict: 'block', score: 93 }),
    entry(-4, 21, 'Demo Officer', 'case.reject', 'pay-tamm.example', 'Official partner page, not a copy', { verdict: 'block', score: 74 }),
    entry(-5, 28, 'Demo Officer', 'watchlist.add', 'rta-fines-uae.online', 'Parked page, may go live'),
    entry(-6, 35, 'Demo Officer', 'takedown.sent', 'demo_req_1', null),
    entry(-7, 41, 'Demo Officer', 'case.confirm', 'tamm-pay.xyz', 'Copies the TAMM payment page', { verdict: 'block', score: 92 }),
    entry(-8, 55, 'Demo Officer', 'case.confirm', 'emiratespost-track.info', 'Asks for a delivery fee by card', { verdict: 'allow', score: 22 }),
  ]
}

function sampleConfirmed(): CaseSummary[] {
  return SAMPLE_DOMAINS.map((domain, i) => ({
    domain,
    state: 'confirmed',
    score: 92 - i * 4,
    verdict: 'block',
    brand: null,
    sources: ['hunter'],
    reports: 0,
    hits: 0,
    first_seen: ago(60 + i * 10),
    evidence_id: null,
    campaign_id: null,
  }))
}

export interface ChainSample {
  seq: number
  domain: string
  hash: string
  at: string
}

export function sampleChainRecords(): ChainSample[] {
  const hashes = ['a41f…9c2e', '7d0b…e518', 'c93a…04fd', '1e6c…b7a2', '58f2…3d91']
  return hashes.map((hash, i) => ({ seq: 25 - i, domain: SAMPLE_DOMAINS[i % SAMPLE_DOMAINS.length], hash, at: ago(4 + i * 7) }))
}

function sampleHelplines(): Helpline[] {
  const brands = ['TAMM', 'DEWA', 'Abu Dhabi Police', 'UAE PASS']
  return ['+971 4 555 0142', '+971 2 555 0198', '+971 50 555 0117', '+971 56 555 0163'].map((phone, i) => ({
    phone,
    brand: brands[i],
    source: 'page',
    domain: SAMPLE_DOMAINS[i],
    first_seen: ago(20 + i * 15),
    confirmed: i < 2,
  }))
}

const LEAD_SAMPLES = [
  { domain: 'tamm-pay.xyz', hours: 31, gsb: 'ahead', vt: 'hit' },
  { domain: 'uaepass-verify.top', hours: 18, gsb: 'ahead', vt: 'ahead' },
  { domain: 'adcb-secure.co', hours: 9, gsb: 'hit', vt: 'ahead' },
] as const

function sampleStats(range: string): Stats {
  const day = range === '7d'
  const count = day ? 7 : 12
  const step = day ? 24 * 60 : 120
  const buckets = Array.from({ length: count }, (_, i) => ago((count - 1 - i) * step))
  const wave = [38, 52, 47, 71, 66, 90, 84, 102, 95, 118, 110, 131]
  const scale = day ? 6 : 1
  const series = buckets.map((bucket, i) => ({
    bucket,
    checks: wave[i % wave.length] * scale,
    candidates: Math.round(wave[i % wave.length] * scale * 0.45),
    confirmed: Math.round((i % 4) + 1) * (day ? 3 : 1),
  }))
  const sum = (key: 'checks' | 'candidates' | 'confirmed') => series.reduce((a, p) => a + p[key], 0)
  return {
    impact: {
      range,
      totals: {
        checks: sum('checks'),
        warn: Math.round(sum('checks') * 0.18),
        block: Math.round(sum('checks') * 0.07),
        candidates: sum('candidates'),
        candidates_by_source: { ct: Math.round(sum('candidates') * 0.8), nrd: Math.round(sum('candidates') * 0.2) },
        reports: day ? 64 : 11,
        confirmed: sum('confirmed'),
        rejected: day ? 9 : 2,
        blocked_hits: { app: day ? 412 : 58, dns: day ? 1290 : 176 },
        blocklist_size: day ? 148 : 131,
        taken_down: day ? 12 : 3,
      },
      series,
      lead_domains: LEAD_SAMPLES.map((d, i) => ({ domain: d.domain, seen: ago(d.hours * 60 + 40), confirmed: ago(d.hours * 60), hours_to_confirm: 0.4 + i * 0.3 })),
    },
    quality: {
      days: 7,
      reviews: 86,
      by_band: [
        { band: 'block', confirmed: 41, cleared: 2, other_reject: 1 },
        { band: 'warn', confirmed: 23, cleared: 14, other_reject: 3 },
        { band: 'allow', confirmed: 1, cleared: 1, other_reject: 0 },
      ],
      block_precision: 41 / 44,
      warn_confirm_rate: 23 / 40,
      false_blocks: 2,
      labels_for_retrain: 86,
      url_model: {
        updated_at: ago(60 * 26),
        train_rows: 48200,
        holdout_rows: 12050,
        officer_phish: 65,
        officer_benign: 21,
        dataset_name: null,
        dataset_date: null,
        held_out: null,
        metrics: [
          { name: 'precision@block', value: 0.962 },
          { name: 'recall@block', value: 0.871 },
          { name: 'precision@warn', value: 0.884 },
          { name: 'recall@warn', value: 0.943 },
        ],
        top_features: ['brand_in_subdomain', 'domain_age_days', 'tld_risk', 'login_words', 'cert_age_hours'],
      },
    },
  }
}

/** Just enough of a case for the Impact page's lead-time table: these domains exist only in the demo. */
function sampleLeadCase(domain: string): Pick<CaseDetail, 'lead_time'> | null {
  const lead = LEAD_SAMPLES.find((d) => d.domain === domain)
  if (!lead) return null
  return {
    lead_time: {
      gsb: { state: lead.gsb, at_least_hours: lead.hours },
      vt: { state: lead.vt, at_least_hours: lead.hours + 4 },
    },
  }
}

const SAMPLE_VERIFY: Verify = { count: 25, intact: true, first_broken: null, message: 'chain intact' }

/** How long the demo waits for real data before showing the sample instead. */
export const DEMO_WAIT_MS = 800

/** The whole sample answer for `path`, used when the real one is too slow during the demo; null when there is none. */
export function demoFallback(path: string): unknown {
  const p = path.split('?')[0]
  if (p === '/v1/admin/takedowns') return { packs: samplePacks(), requests: sampleRequests() }
  if (p === '/v1/admin/takedowns/stats') return sampleTakedownStats()
  if (p === '/v1/admin/stats') return sampleStats(new URLSearchParams(path.split('?')[1] ?? '').get('range') ?? '24h')
  if (p.startsWith('/v1/admin/cases/')) return sampleLeadCase(decodeURIComponent(p.slice('/v1/admin/cases/'.length)))
  if (p === '/v1/admin/audit' && !path.includes('target=')) return { entries: sampleAudit() }
  if (p === '/v1/admin/helplines') return { numbers: sampleHelplines() }
  if (p === '/v1/admin/evidence/verify') return SAMPLE_VERIFY
  if (path === '/v1/admin/queue?state=all') return { cases: sampleConfirmed() }
  return null
}

type Body = Record<string, unknown>

/** Fills an empty list in `data` with sample rows while the demo runs; otherwise returns `data` untouched. */
export function demoFill<T>(path: string, data: T): T {
  if (!demoRunning.value || !data || typeof data !== 'object') return data
  const body = data as Body
  const p = path.split('?')[0]
  const empty = (key: string) => Array.isArray(body[key]) && (body[key] as unknown[]).length === 0
  if (p === '/v1/admin/takedowns' && empty('requests')) return { ...body, packs: samplePacks(), requests: sampleRequests() } as T
  if (p === '/v1/admin/takedowns/stats' && Object.values((body.by_status ?? {}) as Record<string, number>).every((n) => !n)) {
    return sampleTakedownStats() as T
  }
  if (p === '/v1/admin/stats') {
    const sample = sampleStats(new URLSearchParams(path.split('?')[1] ?? '').get('range') ?? '24h')
    const real = data as unknown as Stats
    const impact = real.impact.totals.confirmed && real.impact.lead_domains.length ? real.impact : sample.impact
    const quality = real.quality.reviews ? real.quality : sample.quality
    return { impact, quality } as T
  }
  if (p === '/v1/admin/audit' && !path.includes('target=') && empty('entries')) return { ...body, entries: sampleAudit() } as T
  if (path === '/v1/admin/queue?state=all' && Array.isArray(body.cases)) {
    const cases = body.cases as CaseSummary[]
    if (!cases.some((c) => c.state === 'confirmed')) return { ...body, cases: [...cases, ...sampleConfirmed()] } as T
  }
  return data
}
