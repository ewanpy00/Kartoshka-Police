import { t } from './i18n'
import type { Key } from './i18n'
import type { TakedownRequest } from './types'

// Mirrors the backend default TAKEDOWN_OFFLINE_CHECKS, which the API does not expose.
export const OFFLINE_CHECKS_NEEDED = 2

const CHECKABLE: readonly TakedownRequest['status'][] = ['sent', 'offline_pending', 'reopened', 'closed']

export function statusText(request: Pick<TakedownRequest, 'status' | 'checks_offline'>): string {
  return t(`tdStatus_${request.status}` as Key, { n: request.checks_offline, total: OFFLINE_CHECKS_NEEDED })
}

export function isOffline(request: Pick<TakedownRequest, 'status'>): boolean {
  return request.status === 'closed'
}

export function canCheck(request: Pick<TakedownRequest, 'status'>): boolean {
  return CHECKABLE.includes(request.status)
}

// i18n.ts does not export its dictionary, so an unknown key is detected by t() throwing.
export function translateIfKnown(key: string): string | null {
  try {
    return t(key as Key)
  } catch {
    return null
  }
}
