// Pure functions that turn the merged backend's responses into the shapes in types.ts, so views keep their logic.
//
// Defang rule: the backend sends a raw `domain` beside a defanged `display`. These functions always keep the raw
// value and drop `display`, `display_url` and `display_final_url`; views defang once with `defang()`.
import type {
  AuditEntry,
  CampaignDetail,
  CampaignHeader,
  CaseDetail,
  CaseState,
  CaseSummary,
  EvidenceExport,
  FeedEventType,
  FeedRow,
  Graph,
  Helpline,
  Infrastructure,
  LeadSide,
  Location,
  Pack,
  Reason,
  Verify,
} from './types'

type Raw = Record<string, any> // eslint-disable-line @typescript-eslint/no-explicit-any

const str = (value: unknown): string | null => (typeof value === 'string' && value !== '' ? value : null)
const num = (value: unknown, fallback = 0): number => (typeof value === 'number' && Number.isFinite(value) ? value : fallback)
const list = (value: unknown): Raw[] => (Array.isArray(value) ? (value as Raw[]) : [])
const STATES: readonly CaseState[] = ['open', 'auto_confirmed', 'confirmed', 'rejected']

function state(value: unknown): CaseState {
  return STATES.includes(value as CaseState) ? (value as CaseState) : 'open'
}

// ---------- queue ----------

/** `now` stands in for a missing `last_seen`; the queue age is the time since the latest sighting. */
export function adaptQueueRow(row: Raw, now: string = new Date().toISOString()): CaseSummary {
  return {
    domain: row.domain,
    state: state(row.state),
    score: num(row.score),
    verdict: str(row.verdict) ?? '',
    brand: str(row.brand),
    sources: list(row.sources) as unknown as string[],
    reports: num(row.reports),
    hits: num(row.hits),
    first_seen: str(row.last_seen) ?? now,
    last_seen: str(row.last_seen) ?? undefined,
    evidence_id: str(row.evidence_id),
    campaign_id: str(row.campaign_id),
    rank: typeof row.priority === 'number' ? row.priority : undefined,
  }
}

export function adaptQueue(body: Raw, now?: string): { cases: CaseSummary[] } {
  return { cases: list(body.cases).map((row) => adaptQueueRow(row, now)) }
}

// ---------- case detail ----------

function adaptReason(reason: Raw): Reason {
  // A capped credential reason also has weight_full and capped: true; `weight` is what was applied.
  return { code: reason.code, weight: num(reason.weight), en: reason.en ?? '', ar: reason.ar ?? '', source: reason.source ?? '' }
}

function adaptLocation(location: Raw | null | undefined): Location | null {
  if (!location) return null
  return {
    hosted_in: str(location.hosted_in),
    registered_through: str(location.registered_through),
    network_owner: str(location.network_owner),
    behind_proxy: location.behind_proxy === true,
  }
}

function adaptInfra(infra: Raw | null | undefined, location: Location | null): Infrastructure {
  if (!infra) return {}
  const addresses = list(infra.a) as unknown as string[]
  const ip = str(infra.ip) ?? addresses[0] ?? null
  const asn: Raw = (ip && infra.asn?.[ip]) || {}
  const proxied = location?.behind_proxy === true || !!infra.proxy
  const names = list(infra.ns) as unknown as string[]
  return {
    registrar: str(infra.registrar) ?? str(infra.rdap?.registrar),
    registered_at: str(infra.rdap?.registered),
    name_servers: names.length ? names : (list(infra.rdap?.nameservers) as unknown as string[]),
    ip,
    // Behind a proxy the address belongs to the proxy: its owner says nothing about the host.
    ip_network: proxied ? null : (str(infra.ip_network) ?? str(asn.prefix)),
    ip_owner: proxied ? null : (str(infra.ip_owner) ?? str(asn.name)),
    proxy: str(infra.proxy),
  }
}

function adaptLead(side: Raw | null | undefined): LeadSide | null {
  if (!side) return null
  return { state: side.state, at_least_hours: typeof side.at_least_hours === 'number' ? side.at_least_hours : null }
}

export function adaptCase(raw: Raw): CaseDetail {
  const latest: Raw = raw.latest ?? {}
  const location = adaptLocation(raw.location)
  const reports: Raw = raw.reports ?? {}
  return {
    domain: raw.domain,
    state: state(raw.state),
    score: num(latest.score),
    verdict: str(latest.verdict) ?? '',
    brand: str(latest.brand),
    sources: list(raw.sources) as unknown as string[],
    reports: num(raw.report_count, num(reports.count)),
    hits: num(raw.hit_count),
    first_seen: raw.first_seen,
    last_seen: str(raw.last_seen) ?? undefined,
    rank: typeof raw.rank === 'number' ? raw.rank : undefined,
    evidence_id: str(raw.evidence_id),
    campaign_id: str(raw.campaign_id),
    url: str(raw.url) ?? str(latest.url) ?? '',
    final_url: str(raw.final_url),
    title: str(raw.title),
    reasons: list(raw.reasons).map(adaptReason),
    infrastructure: adaptInfra(raw.infra, location),
    location,
    lead_time: raw.lead_time ? { gsb: adaptLead(raw.lead_time.gsb), vt: adaptLead(raw.lead_time.vt) } : null,
    // The backend has no bilingual page summary yet: null keeps the summary section hidden.
    summary: null,
    checks: list(raw.history).map((c) => ({
      check_id: c.check_id,
      url: '',
      source: c.source,
      verdict: c.verdict,
      score: num(c.score),
      created_at: c.at,
    })),
    report_notes: list(reports.notes).map((n) => ({ id: n.id, note: n.note, created_at: n.created_at })),
    reviews: list(raw.reviews).map((r, index) => ({
      id: index,
      decision: r.decision,
      reason: str(r.reason),
      reviewer: r.reviewer,
      reviewed_at: r.at,
    })),
    has_screenshot: raw.has_screenshot === true,
  }
}

export function adaptEvidence(raw: Raw): EvidenceExport {
  return { id: raw.id, check_id: raw.check_id, seq: num(raw.seq), prev_hash: raw.prev_hash ?? null, hash: raw.hash, created_at: raw.created_at }
}

// ---------- verify, audit, helplines ----------

export function adaptVerify(raw: Raw): Verify {
  const broken = raw.first_broken
  return {
    count: num(raw.count, num(raw.rows)),
    intact: raw.intact === true,
    first_broken: broken ? { id: broken.id, seq: broken.seq, reason: broken.reason } : null,
    message: str(raw.message) ?? (broken ? `record ${broken.id} broken: ${broken.reason}` : 'chain intact'),
  }
}

// feat/app's audit action names, in main's vocabulary (the console labels and the lead-time poller use those).
const AUDIT_ACTIONS: Record<string, string> = {
  'review.confirm': 'case.confirm',
  'review.reject': 'case.reject',
  'case.watch': 'watchlist.add',
  'campaign.merge.officer': 'campaign.merge',
  'takedown.create': 'takedown.pack_built',
}

export function adaptAudit(body: Raw): { entries: AuditEntry[] } {
  return {
    entries: list(body.entries).map((e) => ({
      id: e.id,
      actor: e.actor,
      action: AUDIT_ACTIONS[e.action] ?? e.action,
      target: e.target,
      before: e.before ?? null,
      after: e.after ?? null,
      reason: str(e.reason),
      created_at: e.created_at,
    })),
  }
}

export function adaptHelplines(body: Raw): { numbers: Helpline[] } {
  return {
    numbers: list(body.numbers).map((n) => ({
      phone: n.phone,
      brand: str(n.brand),
      source: n.source,
      domain: n.domain,
      first_seen: n.first_seen,
      confirmed: n.confirmed === true,
    })),
  }
}

// ---------- campaigns ----------

// feat/app: suspected | confirmed. main's pages test for 'campaign' once an officer has confirmed.
const campaignStatus = (status: unknown): string => (status === 'confirmed' ? 'campaign' : 'suspected')

export function adaptCampaignHeader(c: Raw): CampaignHeader {
  return {
    id: c.id,
    name: c.name,
    brand: str(c.brand_id),
    status: campaignStatus(c.status),
    domains: { total: num(c.domain_count), confirmed: num(c.confirmed_count) },
    first_seen: c.first_seen,
    last_activity_at: c.last_activity_at,
    active: c.active === true,
  }
}

export function adaptCampaigns(body: Raw): { campaigns: CampaignHeader[] } {
  return { campaigns: list(body.campaigns).map(adaptCampaignHeader) }
}

export function adaptCampaign(c: Raw): CampaignDetail {
  const { domains: _count, ...header } = adaptCampaignHeader(c)
  void _count
  return {
    ...header,
    domains: list(c.domains).map((d) => ({
      domain: d.domain,
      state: str(d.status) ?? str(d.verdict) ?? '',
      score: typeof d.score === 'number' ? d.score : null,
      evidence_id: str(d.evidence_id),
      excluded: null, // excluded sites leave the campaign on the backend
      tick: d.tick === true,
    })),
    shared: list(c.entities).map((e) => ({
      kind: e.kind,
      value: e.value, // raw; the view defangs it once
      strength: e.strength,
      domain_count: num(e.domain_count),
    })),
    locations: [], // the backend has no per-campaign locations: the existing empty state shows
  }
}

// The backend defangs the label of these node kinds; the graph view defangs again, so hand it the raw value.
const DEFANGED_BY_BACKEND: Record<string, string> = { domain: 'd:', ns: 'ns:', payment: 'payment:' }

export function adaptGraph(g: Raw): Graph {
  return {
    nodes: list(g.nodes).map((n) => {
      const prefix = DEFANGED_BY_BACKEND[n.kind]
      const raw = prefix && typeof n.id === 'string' && n.id.startsWith(prefix) ? n.id.slice(prefix.length) : n.label
      return { data: { id: n.id, label: raw, kind: n.kind } }
    }),
    edges: list(g.edges)
      .filter((e) => e.excluded !== true)
      .map((e) => ({
        data: { id: `${e.source}>${e.target}`, source: e.source, target: e.target, strength: e.strength === 'weak' ? 'weak' : 'strong' },
      })),
  }
}

export function adaptConfirmResult(body: Raw): { confirmed: string[]; skipped: { domain: string; reason: string }[] } {
  return {
    confirmed: list(body.confirmed).map((c) => c.domain),
    skipped: list(body.refused).map((r) => ({ domain: r.domain, reason: r.why ?? r.reason ?? '' })),
  }
}

// ---------- takedowns ----------

/** One backend request is one domain for one recipient; main's page shows one pack per recipient. */
export function adaptPacks(requests: Raw[]): Pack[] {
  const packs = new Map<string, Pack>()
  for (const r of requests) {
    const key = `${r.recipient_kind}|${r.recipient}|${r.pack_sha256}|${r.generated_at}`
    const pack = packs.get(key)
    if (!pack) {
      packs.set(key, {
        id: r.id, // /sent and /pack.zip take any request id of the pack
        recipient_kind: r.recipient_kind,
        recipient: r.recipient,
        domains: [r.domain],
        sha256: r.pack_sha256,
        generated_at: r.generated_at,
        sent_at: str(r.sent_at),
        sent_by: str(r.sent_by),
      })
      continue
    }
    pack.domains.push(r.domain)
    pack.sent_at ??= str(r.sent_at)
    pack.sent_by ??= str(r.sent_by)
  }
  return [...packs.values()]
}

export function adaptTakedownList(body: Raw): { packs: Pack[] } {
  return { packs: adaptPacks(list(body.requests)) }
}

export function adaptTakedownCreated(body: Raw): { packs: Pack[]; without_recipient: string[]; refused: { domain: string; reason: string }[] } {
  return {
    packs: adaptPacks(list(body.requests)),
    without_recipient: [],
    refused: list(body.refused).map((r) => ({ domain: r.domain, reason: r.why ?? r.reason ?? '' })),
  }
}

/** The 409 body is `{detail: {refused: [{domain, display, why}]}}`. */
export function adaptRefused(body: unknown): { domain: string; reason: string }[] {
  const detail = (body as Raw | null)?.detail
  const refused = list(detail?.refused ?? (body as Raw | null)?.refused)
  return refused.map((r) => ({ domain: r.domain, reason: r.why ?? r.reason ?? '' }))
}

// ---------- hunter feed and live events ----------

function hunterRow(entry: Raw): FeedRow {
  return {
    key: `hunter.candidate:${entry.domain}:${entry.first_seen}`,
    type: 'hunter.candidate',
    at: entry.first_seen,
    domain: str(entry.domain),
    brand: str(entry.brand_id),
    verdict: str(entry.verdict),
    score: typeof entry.score === 'number' ? entry.score : null,
  }
}

export function adaptHunterFeed(body: Raw): { rows: FeedRow[] } {
  return { rows: list(body.entries).map(hunterRow) }
}

const EVENT_TYPES: readonly FeedEventType[] = [
  'hunter.candidate',
  'check.verdict',
  'case.reviewed',
  'brand.spike',
  'watchlist.woke',
  'campaign.new_domain',
]

/** One WS envelope `{type, at, data}` as a feed row; null for hello and for events the feed does not show. */
export function adaptEvent(event: Raw): FeedRow | null {
  const type = event?.type as FeedEventType
  if (!EVENT_TYPES.includes(type)) return null
  const d: Raw = event.data ?? {}
  const at: string = event.at ?? d.first_seen ?? ''
  switch (type) {
    case 'hunter.candidate':
      return hunterRow({ ...d, first_seen: d.first_seen ?? at })
    case 'check.verdict':
      return { key: `${type}:${d.check_id}`, type, at, domain: str(d.domain), brand: str(d.brand), verdict: str(d.verdict), score: typeof d.score === 'number' ? d.score : null }
    case 'case.reviewed':
      return { key: `${type}:${d.domain}:${at}`, type, at, domain: str(d.domain), brand: null, verdict: str(d.decision), score: null }
    case 'brand.spike':
      return { key: `${type}:${d.brand_id}:${at}`, type, at, domain: null, brand: str(d.brand_id), verdict: null, score: null }
    case 'watchlist.woke':
    case 'campaign.new_domain':
      return { key: `${type}:${d.domain}:${at}`, type, at, domain: str(d.domain), brand: null, verdict: null, score: null }
  }
}

// ---------- routing by path ----------

const path = (url: string) => url.split('?')[0]

/** Turn the backend's answer to `method url` into main's shape. Unknown routes pass through untouched. */
export function adaptResponse(url: string, body: unknown, method: 'GET' | 'POST' = 'GET'): unknown {
  const p = path(url)
  const raw = body as Raw
  if (method === 'GET') {
    if (p === '/v1/admin/queue') return adaptQueue(raw)
    if (/^\/v1\/admin\/cases\/[^/]+$/.test(p)) return adaptCase(raw)
    if (/^\/v1\/evidence\/[^/]+\.json$/.test(p)) return adaptEvidence(raw)
    if (p === '/v1/admin/evidence/verify') return adaptVerify(raw)
    if (p === '/v1/admin/audit') return adaptAudit(raw)
    if (p === '/v1/admin/helplines') return adaptHelplines(raw)
    if (p === '/v1/admin/hunter/feed') return adaptHunterFeed(raw)
    if (p === '/v1/admin/campaigns') return adaptCampaigns(raw)
    if (/^\/v1\/admin\/campaigns\/[^/]+\/graph$/.test(p)) return adaptGraph(raw)
    if (/^\/v1\/admin\/campaigns\/[^/]+$/.test(p)) return adaptCampaign(raw)
    if (p === '/v1/admin/takedowns') return adaptTakedownList(raw)
    return body
  }
  if (p === '/v1/admin/takedowns') return adaptTakedownCreated(raw)
  if (/^\/v1\/admin\/campaigns\/[^/]+\/confirm$/.test(p)) return adaptConfirmResult(raw)
  return body
}

/** Turn main's request body into the backend's. */
export function adaptRequest(url: string, body: object): object {
  const p = path(url)
  const raw = body as Raw
  if (p === '/v1/admin/takedowns') {
    const { generated_by, ...rest } = raw
    return { ...rest, reviewer: raw.reviewer ?? generated_by }
  }
  if (/^\/v1\/admin\/takedowns\/[^/]+\/sent$/.test(p)) {
    const { sent_by, ...rest } = raw
    return { ...rest, reviewer: raw.reviewer ?? sent_by }
  }
  return body
}

/** Routes that answer one page at a time with `next_cursor`, and the key that holds their rows. */
export function pagedKey(url: string): 'cases' | 'campaigns' | 'requests' | null {
  const p = path(url)
  if (p === '/v1/admin/queue') return 'cases'
  if (p === '/v1/admin/campaigns') return 'campaigns'
  if (p === '/v1/admin/takedowns') return 'requests'
  return null
}
