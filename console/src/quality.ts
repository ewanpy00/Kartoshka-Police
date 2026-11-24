import type { AuditEntry } from './types'

export type DisagreementKind = 'block_rejected' | 'allow_confirmed'

export interface Disagreement {
  id: number
  domain: string
  kind: DisagreementKind
  score: number | null
  reason: string | null
  actor: string
  at: string
}

/**
 * An officer decision that contradicts the verdict the system gave before the review: the system said
 * block and the officer rejected, or the system said allow and the officer confirmed. A warn verdict asks
 * for a review either way, so it never disagrees, and an auto-confirm is not an officer decision.
 */
export function isDisagreement(entry: AuditEntry): DisagreementKind | null {
  const verdict = entry.before?.verdict
  if (entry.action === 'case.reject' && verdict === 'block') return 'block_rejected'
  if (entry.action === 'case.confirm' && verdict === 'allow') return 'allow_confirmed'
  return null
}

export function disagreements(entries: AuditEntry[]): Disagreement[] {
  const found: Disagreement[] = []
  for (const entry of entries) {
    const kind = isDisagreement(entry)
    if (kind === null) continue
    const score = entry.before?.score
    found.push({
      id: entry.id,
      domain: entry.target,
      kind,
      score: typeof score === 'number' ? score : null,
      reason: entry.reason,
      actor: entry.actor,
      at: entry.created_at,
    })
  }
  return found
}
