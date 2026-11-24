// Reports live on this device only: the id and the secret token. No account, no identity.
import { DEMO_REPORTS_KEY, demo, seedReports } from './demo'

export interface SavedReport { id: string; token: string; url: string; at: string }
// Demo mode keeps its own list, so the device's real reports are never mixed with the fixtures.
const KEY = demo ? DEMO_REPORTS_KEY : 'kp.reports'
if (demo) seedReports()

export function savedReports(): SavedReport[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? '[]') as SavedReport[]
  } catch {
    return []
  }
}

export function saveReport(report: SavedReport): void {
  try {
    localStorage.setItem(KEY, JSON.stringify([report, ...savedReports()].slice(0, 50)))
  } catch {
    /* private mode: the report still exists, but this device forgets it */
  }
}

export function forgetReport(id: string): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(savedReports().filter((r) => r.id !== id)))
  } catch {
    /* ignore */
  }
}

export function defang(value: string): string {
  return value.replace(/^https:\/\//i, 'hxxps://').replace(/^http:\/\//i, 'hxxp://').replace(/\./g, '[.]')
}

export function hostOf(url: string): string {
  try {
    return new URL(url).hostname
  } catch {
    return url
  }
}
