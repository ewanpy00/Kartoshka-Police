// Score bands, mirroring core/app/verdict/bands.py: allow below 30, warn 30 to 70 inclusive, block above 70.
export const WARN_FROM = 30
export const BLOCK_ABOVE = 70

export type ScoreBand = 'high' | 'mid' | 'low'

export function band(score: number): ScoreBand {
  if (score > BLOCK_ABOVE) return 'high'
  if (score >= WARN_FROM) return 'mid'
  return 'low'
}

export const isHigh = (score: number): boolean => band(score) === 'high'
