import type { Health } from './types'

export type HealthLevel = 'ok' | 'degraded' | 'down'
export type HealthPart = 'redis' | 'deep' | 'hunter' | 'ai'

/** Hunter counts as fresh while any source produced a candidate within this window. */
export const HUNTER_FRESH_MS = 15 * 60_000

const RANK: Record<HealthLevel, number> = { ok: 0, degraded: 1, down: 2 }

/**
 * The state of each part the strip shows. Down means checks cannot run at all: Redis is failing or no
 * worker serves the deep queue. Degraded means the system runs but an officer should look: deep checks
 * are stale or failed, Hunter has gone quiet, or no AI key is set.
 */
export function healthParts(health: Health, now: number = Date.now()): Record<HealthPart, HealthLevel> {
  const queue = health.deep_queue
  const hunterFresh = health.hunter.some((s) => s.last !== null && now - new Date(s.last).getTime() <= HUNTER_FRESH_MS)
  let deep: HealthLevel = 'ok'
  if (queue === null || queue.workers === 0) deep = 'down'
  else if (queue.failed > 0 || health.checks.deep_stale > 0) deep = 'degraded'
  return {
    redis: health.redis_ok ? 'ok' : 'down',
    deep,
    hunter: hunterFresh ? 'ok' : 'degraded',
    ai: health.ai_key_set ? 'ok' : 'degraded',
  }
}

/** The worst part decides. No answer from core (`null`) is down. */
export function healthLevel(health: Health | null, now: number = Date.now()): HealthLevel {
  if (health === null) return 'down'
  return Object.values(healthParts(health, now)).reduce((worst, level) => (RANK[level] > RANK[worst] ? level : worst), 'ok' as HealthLevel)
}
