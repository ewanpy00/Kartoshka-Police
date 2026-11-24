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
  final_url?: string | null
  summary?: { en: string; ar: string } | null
  checks?: { check_id: string; url: string; source: string; verdict: string; score: number; created_at: string }[]
  report_notes: { id: number; note: string; created_at: string }[]
  reviews: { id: number; decision: string; reason: string | null; reviewer: string; reviewed_at: string }[]
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
  domains: { domain: string; state: string; score: number | null; evidence_id: string | null; excluded: string | null }[]
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

export interface FeedRow {
  key: string
  type: 'hunter.candidate' | 'check.completed'
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
