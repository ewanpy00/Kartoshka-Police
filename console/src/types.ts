// Response shapes of core's /v1/admin/* routes (core/app/api/admin*.py, core/app/admin/*.py).

export interface Reason {
  code: string
  weight: number | null
  source?: string
  en: string
  ar?: string
}

export interface Source {
  id: string
  status: string
  detail?: string
}

export interface QueueRow {
  domain: string
  display: string
  priority: number
  rank_score: number
  score: number
  band: 'allow' | 'warn' | 'block'
  verdict: string | null
  stage: string | null
  brand: string | null
  brand_id: string | null
  check_id: string | null
  evidence_id: string | null
  campaign_id: string | null
  preview: string | null
  reports: number
  hits: number
  checks: number
  sources: string[]
  feeds: string[]
  status: string | null
  last_seen: string | null
  top_reasons: Reason[]
}

export interface QueuePage {
  total: number
  cases: QueueRow[]
  next_cursor: string | null
}

export interface FormField {
  tag?: string
  type?: string
  name?: string
  label?: string
  placeholder?: string
  autocomplete?: string
}

export interface CaseDetail {
  domain: string
  display: string
  status: string | null
  status_source: string | null
  latest: {
    check_id: string
    url: string
    display_url: string
    display_final_url: string | null
    verdict: string
    score: number
    stage: string
    brand: string | null
    brand_id: string | null
    reasons: Reason[]
    sources: Source[]
    features: Record<string, unknown>
    safe_action: { label_en?: string; label_ar?: string; url?: string } | null
    deep_status: string | null
    evidence_id: string | null
    preview: unknown
    created_at: string
  } | null
  page: {
    title?: string
    status?: number
    lang?: string
    text_excerpt?: string
    forms?: { action?: string; method?: string; fields?: FormField[] }[]
    asks_for?: string[]
    phones?: string[]
    payment_hosts?: string[]
    server_ip?: string
    parked?: boolean
    cloaking?: unknown
  } | null
  infra: {
    a?: string[]
    ns?: string[]
    mx?: string[]
    asn?: Record<string, { asn: string; name?: string; country?: string }>
    rdap?: { registrar?: string; created?: string; abuse_emails?: string[]; status?: string[] } | null
  } | null
  visual: { brand_id: string; similarity: number } | null
  kit: { kit_hash?: string; favicon_sha256?: string } | null
  discovery: { source: string; first_seen: string; display_url: string; brand_id: string | null }[]
  reports: { count: number; notes: { at: string; note: string }[] }
  hits: Record<string, number>
  campaign: { id: string; name: string; domain_count: number; confirmed_count: number } | null
  watchlist: { reason: string; last_status: string; next_check_at: string; expires_at: string } | null
  reviews: { decision: string; reason: string | null; reviewer: string; note: string | null; at: string }[]
  history: { check_id: string; source: string; verdict: string; score: number; stage: string; at: string }[]
}

export interface FeedRow {
  id: number
  source: string
  domain: string
  display: string
  display_url: string
  brand_id: string | null
  detail: string | null
  first_seen: string
  verdict: string | null
  score: number | null
  stage: string | null
}

export interface WatchRow {
  domain: string
  display: string
  reason: string
  last_status: string | null
  last_checked_at: string | null
  checks_done: number
  next_check_at: string
  expires_at: string
}

export interface CampaignSummary {
  id: string
  name: string | null
  brand_id: string | null
  status: 'suspected' | 'confirmed'
  domain_count: number
  confirmed_count: number
  first_seen: string
  last_activity_at: string | null
  active: boolean
}

export interface CampaignDomain {
  domain: string
  display: string
  status: string | null
  score: number | null
  verdict: string | null
  evidence_id: string | null
  brand_id: string | null
  last_seen: string | null
  links: string[]
  tick: boolean
}

export interface CampaignEntity {
  kind: string
  value: string
  label: string
  strength: 'strong' | 'weak'
  domain_count: number
  in_campaign: number
}

export interface CampaignDetail extends CampaignSummary {
  domains: CampaignDomain[]
  entities: CampaignEntity[]
}

export interface GraphNode {
  id: string
  kind: string
  label: string
  status?: string | null
  score?: number | null
  domain_count?: number
  hub?: boolean
}

export interface GraphEdge {
  source: string
  target: string
  strength: 'strong' | 'weak'
  excluded: boolean
}

export interface CampaignGraph {
  nodes: GraphNode[]
  edges: GraphEdge[]
  collapsed: { kind: string; count: number }[]
}

export interface Lead {
  domain: string
  display: string
  via: { kind: string; label: string; strong: boolean }[]
  status: string | null
  score: number | null
  campaign: string | null
}

export interface Takedown {
  id: string
  domain: string
  display: string
  campaign_id: string | null
  recipient_kind: string
  recipient: string
  form: boolean
  status: 'pack_ready' | 'sent' | 'offline_pending' | 'closed' | 'reopened'
  overdue: boolean
  pack_sha256: string | null
  generated_at: string
  sent_at: string | null
  sent_by: string | null
  offline_at: string | null
  offline_reason: string | null
  checks_offline: number
}

export interface TakedownStats {
  by_status: Record<string, number>
  overdue: number
  median_hours_to_offline: number | null
  recipients: Record<string, { requests: number; closed: number; median_hours: number | null }>
  sla_hours: number
}

export interface LeadTimeRow {
  domain: string
  display: string
  brand_id: string | null
  seen: string
  confirmed: string | null
  hours_to_confirm: number | null
  lead_vs_gsb_h: number | null
  lead_vs_gsb_open: boolean
  lead_vs_vt_h: number | null
  lead_vs_vt_open: boolean
}

export interface Stats {
  range: string
  totals: {
    checks: number
    warn: number
    block: number
    candidates: number
    candidates_by_source: Record<string, number>
    reports: number
    confirmed: number
    rejected: number
    blocked_hits: Record<string, number>
    blocklist_size: number
    taken_down: number
  }
  series: { buckets: string[]; checks: number[]; candidates: number[]; confirmed: number[] }
  lead_time: {
    domains: LeadTimeRow[]
    median_hours_to_confirm: number | null
    median_lead_vs_gsb_h: number | null
    median_lead_vs_vt_h: number | null
    flagged_by_gsb_later: number
    not_flagged_by_gsb_yet: number
  }
  takedown_median_hours: number | null
  quality: {
    days: number
    reviews: number
    by_band: Record<string, { confirmed: number; cleared: number; other_reject: number }>
    block_precision: number | null
    warn_confirm_rate: number | null
    false_blocks: number
    url_model: { updated_at: string; score: number | null; metrics: Record<string, unknown> | null } | null
    labels_for_retrain: number
  }
}

export interface AdminHealth {
  checked_at: string
  redis: string
  deep_queue?: { waiting: number; failed: number; workers: number }
  hunter: Record<string, { last: string; last_24h: number }>
  checks: { last: string | null; last_hour: number; deep_running: number; deep_stale: number }
  models: Record<string, { updated_at: string; score: number | null } | null>
  evidence: { records: number }
  blocklist_version: number
  ai: string
}
