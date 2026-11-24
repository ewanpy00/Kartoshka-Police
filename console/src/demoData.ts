// Sample data shown only while the demo tour runs, so pages with no real data yet still look complete.
//
// Rules: real data wins when it arrives within DEMO_WAIT_MS (a sample fills a list only when the real list is
// empty), nothing here is ever sent to core, and everything disappears when the demo stops, because the pages
// that can show samples load real data again. All recipients, phone numbers and domains are made up.
import { demoRunning } from './demo'
import type {
  AuditEntry,
  CampaignDetail,
  CampaignHeader,
  CaseDetail,
  CaseSummary,
  Graph,
  Helpline,
  Pack,
  Stats,
  TakedownRequest,
  TakedownStats,
  Verify,
} from './types'

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

/** Open cases for the queue while the real queue is slow: they exist only in the demo. */
const SAMPLE_CASES = [
  { domain: 'tamm-pay.xyz', brand: 'TAMM', score: 94, sources: ['gatekeeper', 'hunter'], reports: 3, hits: 41, minutes: 18 },
  { domain: 'uaepass-verify.top', brand: 'UAE PASS', score: 91, sources: ['hunter'], reports: 1, hits: 12, minutes: 32 },
  { domain: 'adcb-secure.co', brand: 'ADCB', score: 86, sources: ['user_report'], reports: 2, hits: 7, minutes: 47 },
  { domain: 'rta-fines-uae.online', brand: 'RTA', score: 78, sources: ['hunter'], reports: 0, hits: 3, minutes: 65 },
] as const

/** A domain or campaign that exists only in the demo, so a page can leave it as soon as the demo stops. */
export function isDemoOnly(id: string): boolean {
  return id === SAMPLE_CAMPAIGN_ID || SAMPLE_CASES.some((c) => c.domain === id)
}

function sampleQueue(): CaseSummary[] {
  return SAMPLE_CASES.map((c, i) => ({
    domain: c.domain,
    state: 'open',
    score: c.score,
    verdict: 'block',
    brand: c.brand,
    sources: [...c.sources],
    reports: c.reports,
    hits: c.hits,
    first_seen: ago(c.minutes),
    last_seen: ago(2 + i),
    evidence_id: `demo_ev_${i + 1}`,
    campaign_id: null,
  }))
}

/** A whole case for a sample domain: the case card while the real queue is slow, and Impact's lead time. */
function sampleCase(domain: string): CaseDetail | null {
  const index = SAMPLE_CASES.findIndex((c) => c.domain === domain)
  if (index < 0) return null
  const c = SAMPLE_CASES[index]
  const lead = LEAD_SAMPLES.find((d) => d.domain === domain)
  const brand = c.brand
  return {
    ...sampleQueue()[index],
    url: `https://${domain}/pay`,
    final_url: `https://${domain}/pay/card`,
    title: `${brand} | Pay your traffic fine`,
    summary: {
      en: `A new site copying the ${brand} payment page. It asks for the card number, CVV and the one-time code.`,
      ar: `موقع جديد ينسخ صفحة الدفع الخاصة بـ ${brand}. يطلب رقم البطاقة ورمز التحقق والرمز المؤقت.`,
    },
    reasons: [
      { code: 'brand_lookalike', weight: 30, en: `The name imitates ${brand}`, ar: `الاسم يقلّد ${brand}`, source: 'url' },
      { code: 'card_form', weight: 25, en: 'The page asks for card number, CVV and OTP', ar: 'الصفحة تطلب رقم البطاقة ورمز التحقق والرمز المؤقت', source: 'page' },
      { code: 'new_domain', weight: 20, en: 'Registered 2 days ago', ar: 'سُجّل قبل يومين', source: 'whois' },
      { code: 'visual_match', weight: 12, en: `The page looks like the real ${brand} site`, ar: `الصفحة تشبه موقع ${brand} الحقيقي`, source: 'screenshot' },
      { code: 'risky_tld', weight: 7, en: 'A domain ending often used for scams', ar: 'امتداد نطاق يُستخدم كثيراً في الاحتيال', source: 'url' },
    ],
    infrastructure: {
      registrar: 'Registrar Example Ltd.',
      registered_at: ago(2 * 24 * 60),
      name_servers: ['ns1.hosting.example', 'ns2.hosting.example'],
      ip: '203.0.113.24',
      ip_owner: 'Hosting Example',
    },
    location: { hosted_in: 'NL', registered_through: 'Registrar Example Ltd.', network_owner: 'Hosting Example', behind_proxy: false },
    lead_time: lead
      ? { gsb: { state: lead.gsb, at_least_hours: lead.hours }, vt: { state: lead.vt, at_least_hours: lead.hours + 4 } }
      : null,
    asks_for: ['card', 'cvv', 'otp'],
    checks: [],
    report_notes: [],
    reviews: [],
    has_screenshot: true,
  }
}

/** The demo cases' screenshot: a plain sketch of a fake payment page, with no real logo. */
export const SAMPLE_SHOT_SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="960" height="600" viewBox="0 0 960 600" font-family="Arial, sans-serif">
<rect width="960" height="600" fill="#f4f5f7"/>
<rect width="960" height="44" fill="#e2e5ea"/><circle cx="24" cy="22" r="6" fill="#c9ced6"/><circle cx="44" cy="22" r="6" fill="#c9ced6"/><circle cx="64" cy="22" r="6" fill="#c9ced6"/>
<rect x="96" y="10" width="520" height="24" rx="12" fill="#fff"/><text x="112" y="27" font-size="13" fill="#555">https://tamm-pay.xyz/pay</text>
<rect y="44" width="960" height="64" fill="#1d3b5a"/><text x="40" y="84" font-size="22" fill="#fff" font-weight="bold">Government Services</text>
<text x="40" y="160" font-size="28" fill="#1d2733" font-weight="bold">Pay your traffic fine</text>
<text x="40" y="192" font-size="15" fill="#5b6573">Fine AED 500 · Pay within 24 hours to avoid a penalty</text>
<rect x="40" y="220" width="560" height="320" rx="10" fill="#fff" stroke="#d8dce2"/>
<text x="64" y="260" font-size="14" fill="#333">Card number</text><rect x="64" y="270" width="512" height="40" rx="6" fill="#f8f9fb" stroke="#c9ced6"/>
<text x="64" y="340" font-size="14" fill="#333">Expiry</text><rect x="64" y="350" width="240" height="40" rx="6" fill="#f8f9fb" stroke="#c9ced6"/>
<text x="336" y="340" font-size="14" fill="#333">CVV</text><rect x="336" y="350" width="240" height="40" rx="6" fill="#f8f9fb" stroke="#c9ced6"/>
<text x="64" y="420" font-size="14" fill="#333">One-time code (OTP)</text><rect x="64" y="430" width="512" height="40" rx="6" fill="#f8f9fb" stroke="#c9ced6"/>
<rect x="64" y="486" width="512" height="40" rx="6" fill="#2f7d4f"/><text x="320" y="512" font-size="16" fill="#fff" text-anchor="middle" font-weight="bold">Pay now</text>
<rect x="640" y="220" width="280" height="140" rx="10" fill="#fff" stroke="#d8dce2"/><text x="660" y="256" font-size="15" fill="#1d2733" font-weight="bold">Fine details</text>
<text x="660" y="288" font-size="13" fill="#5b6573">Speeding · Sheikh Zayed Rd</text><text x="660" y="314" font-size="13" fill="#5b6573">Amount: AED 500</text>
</svg>`

/** The demo screenshot for a sample case's evidence; null for anything else. */
export function demoBlob(path: string): Blob | null {
  if (!demoRunning.value || !/^\/v1\/admin\/evidence\/demo_ev_\d+\/screenshot\.png$/.test(path)) return null
  return new Blob([SAMPLE_SHOT_SVG], { type: 'image/svg+xml' })
}

const SAMPLE_CAMPAIGN_ID = 'demo_cmp_1'

function sampleCampaignHeader(): CampaignHeader {
  return {
    id: SAMPLE_CAMPAIGN_ID,
    name: 'Fake fine payments · since 22 Nov 2026',
    brand: 'TAMM',
    status: 'campaign',
    domains: { total: SAMPLE_CASES.length, confirmed: 1 },
    first_seen: ago(3 * 24 * 60),
    last_activity_at: ago(18),
    active: true,
  }
}

function sampleCampaign(): CampaignDetail {
  const { domains: _count, ...header } = sampleCampaignHeader()
  return {
    ...header,
    domains: SAMPLE_CASES.map((c, i) => ({
      domain: c.domain,
      state: i === 0 ? 'confirmed' : 'open',
      score: c.score,
      evidence_id: `demo_ev_${i + 1}`,
      excluded: null,
    })),
    shared: [
      { kind: 'ns', value: 'ns1.hosting.example', strength: 'strong', domain_count: 4 },
      { kind: 'ip', value: '203.0.113.24', strength: 'strong', domain_count: 3 },
      { kind: 'registrar', value: 'Registrar Example Ltd.', strength: 'weak', domain_count: 4 },
    ],
    locations: [{ hosted_in: 'NL', registered_through: 'Registrar Example Ltd.', network_owner: 'Hosting Example', behind_proxy: false, domains: 4 }],
  }
}

function sampleGraph(): Graph {
  const nodes: Graph['nodes'] = [
    ...SAMPLE_CASES.map((c) => ({ data: { id: `d:${c.domain}`, label: c.domain, kind: 'domain' } })),
    { data: { id: 'ns:ns1.hosting.example', label: 'ns1.hosting.example', kind: 'ns' } },
    { data: { id: 'ip:203.0.113.24', label: '203.0.113.24', kind: 'ip' } },
    { data: { id: 'phone:+971 4 555 0142', label: '+971 4 555 0142', kind: 'phone' } },
  ]
  const edge = (source: string, target: string, strength: 'strong' | 'weak' = 'strong') => ({
    data: { id: `${source}>${target}`, source, target, strength },
  })
  const d = SAMPLE_CASES.map((c) => `d:${c.domain}`)
  return {
    nodes,
    edges: [
      ...d.map((id) => edge(id, 'ns:ns1.hosting.example')),
      ...d.slice(0, 3).map((id) => edge(id, 'ip:203.0.113.24')),
      edge(d[0], 'phone:+971 4 555 0142'),
      edge(d[3], 'phone:+971 4 555 0142', 'weak'),
    ],
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
  if (p.startsWith('/v1/admin/cases/')) return sampleCase(decodeURIComponent(p.slice('/v1/admin/cases/'.length)))
  if (path === '/v1/admin/queue?state=open') return { cases: sampleQueue() }
  if (p === '/v1/admin/campaigns') return { campaigns: [sampleCampaignHeader()] }
  if (p === `/v1/admin/campaigns/${SAMPLE_CAMPAIGN_ID}`) return sampleCampaign()
  if (p === `/v1/admin/campaigns/${SAMPLE_CAMPAIGN_ID}/graph`) return sampleGraph()
  if (path === '/v1/admin/queue?state=auto_confirmed') return { cases: [] }
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
