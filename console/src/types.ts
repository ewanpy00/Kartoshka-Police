export type CaseState = 'open' | 'auto_confirmed' | 'confirmed' | 'rejected'

export interface CaseSummary {
  domain: string
  state: CaseState
  score: number
  verdict: string
  brand: string | null
  sources: string[]
  reports: number
  hits: number
  first_seen: string
  evidence_id: string | null
  campaign_id: string | null
  last_seen?: string
  rank?: number
}

export interface Reason {
  code: string
  weight: number
  en: string
  ar: string
  source: string
}

export interface Location {
  hosted_in: string | null
  registered_through: string | null
  network_owner: string | null
  behind_proxy: boolean
}

export interface LeadSide {
  state: 'not_polled' | 'ahead' | 'hit'
  at_least_hours: number | null
}

export interface Infrastructure {
  registrar?: string | null
  registered_at?: string | null
  name_servers?: string[]
  ip?: string | null
  ip_network?: string | null
  ip_owner?: string | null
  proxy?: string | null
}

export interface CaseDetail extends CaseSummary {
  url: string
  title: string | null
  reasons: Reason[]
  infrastructure: Infrastructure
  location?: Location | null
  lead_time?: { gsb?: LeadSide | null; vt?: LeadSide | null } | null
  asks_for?: string[]
  final_url?: string | null
  summary?: { en: string; ar: string } | null
  checks?: { check_id: string; url: string; source: string; verdict: string; score: number; created_at: string }[]
  report_notes: { id: number | string; note: string; created_at: string }[]
  reviews: { id: number | string; decision: string; reason: string | null; reviewer: string; reviewed_at: string }[]
  has_screenshot: boolean
}

export interface CampaignHeader {
  id: string
  name: string
  brand: string | null
  status: string
  domains: { total: number; confirmed: number }
  first_seen: string
  last_activity_at: string
  active: boolean
}

export interface CampaignDetail extends Omit<CampaignHeader, 'domains'> {
  domains: {
    domain: string
    state: string
    score: number | null
    evidence_id: string | null
    excluded: string | null
    /** The backend's own advice on pre-ticking the site for "Confirm all". */
    tick?: boolean
  }[]
  shared: { kind: string; value: string; strength: string; domain_count: number }[]
  locations: (Location & { domains: number })[]
}

export interface Graph {
  nodes: { data: { id: string; label: string; kind: string } }[]
  edges: { data: { id: string; source: string; target: string; strength: 'strong' | 'weak' } }[]
}

export interface Pack {
  id: string
  recipient_kind: string
  recipient: string
  domains: string[]
  sha256: string
  generated_at: string
  sent_at: string | null
  sent_by: string | null
}

export interface Helpline {
  phone: string
  brand: string | null
  source: string
  domain: string
  first_seen: string
  confirmed: boolean
}

export type FeedEventType =
  | 'hunter.candidate'
  | 'check.verdict'
  | 'case.reviewed'
  | 'brand.spike'
  | 'watchlist.woke'
  | 'campaign.new_domain'

export interface FeedRow {
  key: string
  type: FeedEventType
  at: string
  domain: string | null
  brand: string | null
  verdict: string | null
  score: number | null
}

export interface Verify {
  count: number
  intact: boolean
  first_broken: { id: string; seq: number; reason: string } | null
  message: string
}

export interface AuditEntry {
  id: number
  actor: string
  action: string
  target: string
  before: Record<string, unknown> | null
  after: Record<string, unknown> | null
  reason: string | null
  created_at: string
}

export interface EvidenceExport {
  id: string
  check_id: string
  seq: number
  prev_hash: string | null
  hash: string
  created_at: string
}

export interface ImpactTotals {
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

export interface ImpactStats {
  range: string
  totals: ImpactTotals
  series: { bucket: string; checks: number; candidates: number; confirmed: number }[]
  lead_domains: { domain: string; seen: string | null; confirmed: string | null; hours_to_confirm: number | null }[]
}

export type Band = 'block' | 'warn' | 'allow'

export interface UrlModel {
  updated_at: string | null
  train_rows: number | null
  holdout_rows: number | null
  officer_phish: number | null
  officer_benign: number | null
  dataset_name: string | null
  dataset_date: string | null
  held_out: boolean | null
  metrics: { name: string; value: number }[]
  top_features: string[]
}

export interface QualityStats {
  days: number
  reviews: number
  by_band: { band: Band; confirmed: number; cleared: number; other_reject: number }[]
  block_precision: number | null
  warn_confirm_rate: number | null
  false_blocks: number
  labels_for_retrain: number
  url_model: UrlModel | null
}

export interface Stats {
  impact: ImpactStats
  quality: QualityStats
}

export interface WatchRow {
  domain: string
  reason: string
  brand: string | null
  last_status: string
  last_checked_at: string | null
  checks_done: number
  next_check_at: string | null
  expires_at: string | null
}

export interface Watchlist {
  total: number
  rows: WatchRow[]
}

export interface Budget {
  used: number
  limit: number | null
  reached: boolean
}

export interface Health {
  checked_at: string
  redis_ok: boolean
  deep_queue: { waiting: number; failed: number; workers: number } | null
  hunter: { source: string; last: string | null; last_24h: number }[]
  checks: { last: string | null; last_hour: number; deep_running: number; deep_stale: number }
  models: { name: string; updated_at: string | null; score: number | null }[]
  evidence_records: number
  blocklist_version: string | null
  ai_key_set: boolean
  budget: { ai: Budget; deep: Budget }
}

export type TakedownStatus = 'pack_ready' | 'sent' | 'offline_pending' | 'closed' | 'reopened'

export interface TakedownRequest {
  id: string
  domain: string
  campaign_id: string | null
  recipient_kind: string
  recipient: string
  form: boolean
  status: TakedownStatus | 'unknown'
  overdue: boolean
  pack_sha256: string
  generated_at: string
  sent_at: string | null
  sent_by: string | null
  offline_at: string | null
  offline_reason: string | null
  checks_offline: number
}

export type TakedownDetail = TakedownRequest & { pack: TakedownRequest[] }

export interface TakedownStats {
  by_status: Record<TakedownStatus, number>
  overdue: number
  median_hours_to_offline: number | null
  recipients: { kind: string; requests: number; closed: number; median_hours: number | null }[]
  sla_hours: number
}

export interface ExcludeResult {
  domain: string
  domain_count: number
}

export interface MergeResult {
  id: string
  merged: string[]
}

export interface PivotLead {
  domain: string
  via: { kind: string; label: string; strong: boolean }[]
  status: string | null
  score: number | null
  campaign: string | null
}

export interface Pivot {
  total: number
  leads: PivotLead[]
}

export interface EntityCard {
  kind: string
  value: string
  label: string
  first_seen: string | null
  domain_count: number
  hub: boolean
  domains: { domain: string; status: string | null; strength: 'strong' | 'weak'; excluded: boolean; campaign: string | null; score: number | null }[]
}
