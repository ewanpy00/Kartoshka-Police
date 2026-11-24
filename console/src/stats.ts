import { ref, type Ref } from 'vue'
import { apiJson } from './api'
import type { AuditEntry, CaseDetail, CaseSummary, Verify } from './types'

const awaiting = ref<number | null>(null)
const autoConfirmedToday = ref<number | null>(null)
const chain = ref<{ intact: boolean; count: number; brokenSeq: number | null } | null>(null)
const medianLead = ref<{ hours: number; cases: number } | null>(null)
let medianStarted = false

const STORAGE_KEY = 'kp.medianLead'
const MAX_CASES = 30
const CONCURRENCY = 4

export function leadHours(lead: CaseDetail['lead_time']): number | null {
  if (!lead) return null
  const counted: number[] = []
  for (const side of [lead.gsb, lead.vt]) {
    if (side && (side.state === 'ahead' || side.state === 'hit') && typeof side.at_least_hours === 'number') {
      counted.push(side.at_least_hours)
    }
  }
  return counted.length ? Math.min(...counted) : null
}

export function useStats() {
  return { awaiting, autoConfirmedToday, chain, medianLead } as {
    awaiting: Ref<number | null>
    autoConfirmedToday: Ref<number | null>
    chain: Ref<{ intact: boolean; count: number; brokenSeq: number | null } | null>
    medianLead: Ref<{ hours: number; cases: number } | null>
  }
}

function sameLocalDay(iso: string, now: Date): boolean {
  const d = new Date(iso)
  return (
    d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth() && d.getDate() === now.getDate()
  )
}

export async function refreshStats(): Promise<void> {
  await Promise.all([
    (async () => {
      try {
        const data = await apiJson<{ cases: CaseSummary[] }>('/v1/admin/queue?state=open')
        awaiting.value = data.cases.length
      } catch {
        awaiting.value = null
      }
    })(),
    (async () => {
      try {
        const data = await apiJson<{ entries: AuditEntry[] }>('/v1/admin/audit?limit=500')
        const now = new Date()
        autoConfirmedToday.value = data.entries.filter(
          (e) => e.action === 'case.auto_confirm' && sameLocalDay(e.created_at, now),
        ).length
      } catch {
        autoConfirmedToday.value = null
      }
    })(),
    (async () => {
      try {
        const v = await apiJson<Verify>('/v1/admin/evidence/verify')
        chain.value = { intact: v.intact, count: v.count, brokenSeq: v.first_broken?.seq ?? null }
      } catch {
        chain.value = null
      }
    })(),
  ])
}

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  const value = sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2
  return Math.round(value * 10) / 10
}

async function computeMedianLead(): Promise<void> {
  try {
    let cached: string | null = null
    try {
      cached = sessionStorage.getItem(STORAGE_KEY)
    } catch {
      cached = null
    }
    if (cached !== null) {
      medianLead.value = JSON.parse(cached) as { hours: number; cases: number } | null
      return
    }
    const data = await apiJson<{ entries: AuditEntry[] }>('/v1/admin/audit?limit=500')
    const targets: string[] = []
    for (const e of data.entries) {
      if (e.action === 'watchlist.add' && !targets.includes(e.target)) targets.push(e.target)
      if (targets.length >= MAX_CASES) break
    }
    const values: number[] = []
    let next = 0
    const worker = async () => {
      while (next < targets.length) {
        const target = targets[next++]
        try {
          const detail = await apiJson<CaseDetail>(`/v1/admin/cases/${encodeURIComponent(target)}`)
          const h = leadHours(detail.lead_time)
          if (h !== null) values.push(h)
        } catch {
          // Individual failures are ignored.
        }
      }
    }
    await Promise.all(Array.from({ length: CONCURRENCY }, worker))
    const result = values.length ? { hours: median(values), cases: values.length } : null
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(result))
    } catch {
      // Storage may be blocked.
    }
    medianLead.value = result
  } catch {
    medianLead.value = null
  }
}

export function startMedianLead(): void {
  if (medianStarted) return
  medianStarted = true
  void computeMedianLead()
}

export function _resetStatsForTest(): void {
  awaiting.value = null
  autoConfirmedToday.value = null
  chain.value = null
  medianLead.value = null
  medianStarted = false
}
