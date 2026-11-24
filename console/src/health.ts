import { apiFetch } from './api'

export interface Health {
  status: string
  db: string
  redis: string
}

export type HealthResult =
  | { state: 'healthy'; health: Health }
  | { state: 'degraded'; health: Health }
  | { state: 'unreachable' }

export async function checkHealth(): Promise<HealthResult> {
  try {
    const response = await apiFetch('/healthz')
    if (!response.ok && response.status !== 503) {
      return { state: 'unreachable' }
    }
    const health: Health = await response.json()
    return { state: response.ok ? 'healthy' : 'degraded', health }
  } catch {
    return { state: 'unreachable' }
  }
}
