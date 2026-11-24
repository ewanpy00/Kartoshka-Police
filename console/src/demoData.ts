// Sample data shown only while the demo tour runs, so pages with no real data yet still look complete.
//
// Rules: real data wins when it arrives within DEMO_WAIT_MS (a sample fills a list only when the real list is
// empty), nothing here is ever sent to core, and everything disappears when the demo stops, because the pages
// that can show samples load real data again. All recipients, phone numbers and domains are made up.
import { demoRunning } from './demo'
import type { AuditEntry, CaseSummary, Helpline, Pack, Verify } from './types'

function ago(minutes: number): string {
  return new Date(Date.now() - minutes * 60_000).toISOString()
}

const SAMPLE_DOMAINS = ['tamm-pay.xyz', 'uaepass-verify.top', 'adcb-secure.co', 'rta-fines-uae.online']

function samplePacks(): Pack[] {
  return [
    {
      id: 'demo_pack_1',
      recipient_kind: 'Registrar',
      recipient: 'abuse@registrar.example',
      domains: ['tamm-pay.xyz', 'rta-fines-uae.online'],
      sha256: '9f2c4e81b07a5d3361c2f0e9a4b85d17c6e3a2f09b8d4c1e7a5f3b2d6c9e0a14',
      generated_at: ago(42),
      sent_at: ago(35),
      sent_by: 'Demo Officer',
    },
    {
      id: 'demo_pack_2',
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

function sampleAudit(): AuditEntry[] {
  const entry = (id: number, minutes: number, actor: string, action: string, target: string, reason: string | null): AuditEntry => ({
    id,
    actor,
    action,
    target,
    before: null,
    after: null,
    reason,
    created_at: ago(minutes),
  })
  return [
    entry(-1, 3, 'Demo Officer', 'takedown.pack_built', 'demo_pack_2', null),
    entry(-2, 9, 'Demo Officer', 'case.confirm', 'adcb-secure.co', 'Asks for card number and OTP'),
    entry(-3, 14, 'system', 'case.auto_confirm', 'uaepass-verify.top', 'Deep score over 90 with a login form'),
    entry(-4, 21, 'Demo Officer', 'case.reject', 'tamm.abudhabi', 'Official domain'),
    entry(-5, 28, 'Demo Officer', 'watchlist.add', 'rta-fines-uae.online', 'Parked page, may go live'),
    entry(-6, 35, 'Demo Officer', 'takedown.sent', 'demo_pack_1', null),
    entry(-7, 41, 'Demo Officer', 'case.confirm', 'tamm-pay.xyz', 'Copies the TAMM payment page'),
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

const SAMPLE_VERIFY: Verify = { count: 25, intact: true, first_broken: null, message: 'chain intact' }

/** How long the demo waits for real data before showing the sample instead. */
export const DEMO_WAIT_MS = 800

/** The whole sample answer for `path`, used when the real one is too slow during the demo; null when there is none. */
export function demoFallback(path: string): unknown {
  const p = path.split('?')[0]
  if (p === '/v1/admin/takedowns') return { packs: samplePacks() }
  if (p === '/v1/admin/audit') return { entries: sampleAudit() }
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
  if (p === '/v1/admin/takedowns' && empty('packs')) return { ...body, packs: samplePacks() } as T
  if (p === '/v1/admin/audit' && empty('entries')) return { ...body, entries: sampleAudit() } as T
  if (path === '/v1/admin/queue?state=all' && Array.isArray(body.cases)) {
    const cases = body.cases as CaseSummary[]
    if (!cases.some((c) => c.state === 'confirmed')) return { ...body, cases: [...cases, ...sampleConfirmed()] } as T
  }
  return data
}
