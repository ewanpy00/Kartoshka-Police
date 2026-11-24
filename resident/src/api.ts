// Resident routes only. No write token: the device sends a random id for rate limits (not an identity).
export interface Reason { code: string; weight: null; source: string; en: string; ar: string }
export interface Source { id: string; status: 'hit' | 'clean' | 'unknown' | 'skipped'; detail?: string | null }
export interface SafeAction { label_en: string; label_ar: string; url: string }
export interface Verdict {
  check_id: string
  url: string
  final_url: string | null
  verdict: 'allow' | 'warn' | 'block' | 'pending'
  score: number
  stage: string
  brand: string | null
  safe_action: SafeAction | null
  reasons: Reason[]
  sources: Source[]
  preview: { screenshot: string | null; asks_for: string[]; title: string | null } | null
  deep_status: string | null
  evidence_id: string | null
}
export interface Step { id: string; done: boolean; at: string | null; en: string; ar: string }
export interface ReportStatus {
  report_id: string
  url: string
  status: string
  verdict: string
  brand: string | null
  created_at: string
  blocked_count: number
  steps: Step[]
}
export interface RadarBrand {
  brand_id: string
  brand: string
  brand_ar: string
  confirmed: number
  suspected: number
  active: number
  new_today: number
  yesterday: number
  examples: string[]
  tip_en: string | null
  tip_ar: string | null
  safe_action: SafeAction | null
}
export interface Radar {
  generated_at: string
  totals: { active: number; confirmed: number; suspected: number; new_today: number; yesterday: number }
  headlines: { category: string; active: number; new_today: number; en: string; ar: string }[]
  brands: RadarBrand[]
}
export interface SmsResult {
  links: Verdict[]
  found_links: number
  text: { category: string | null; category_en: string | null; category_ar: string | null; urgent: boolean; by: string }
}

function deviceId(): string {
  try {
    let id = localStorage.getItem('kp.device')
    if (!id) {
      id = crypto.randomUUID()
      localStorage.setItem('kp.device', id)
    }
    return id
  } catch {
    return 'anonymous'
  }
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set('X-Device-Id', deviceId())
  if (init.body) headers.set('Content-Type', 'application/json')
  const response = await fetch(`/api${path}`, { ...init, headers })
  if (!response.ok) {
    let message = `${response.status}`
    try {
      const body = await response.json()
      message = typeof body.detail === 'string' ? body.detail : Array.isArray(body.detail) ? body.detail[0]?.msg ?? message : message
    } catch {
      /* not JSON */
    }
    throw new ApiError(response.status, message)
  }
  return response.json() as Promise<T>
}

export const checkLink = (url: string, source = 'resident') =>
  call<Verdict>('/v1/check', { method: 'POST', body: JSON.stringify({ url, source, mode: 'fast' }) })
export const getCheck = (id: string) => call<Verdict>(`/v1/check/${encodeURIComponent(id)}?view=resident`)
export const askPreview = (url: string) => call<Verdict>('/v1/preview', { method: 'POST', body: JSON.stringify({ url }) })
export const sendReport = (url: string, note: string) =>
  call<{ report_id: string; token: string; check_id: string }>('/v1/report', { method: 'POST', body: JSON.stringify({ url, note }) })
export const reportStatus = (id: string, token: string) =>
  call<ReportStatus>(`/v1/reports/${encodeURIComponent(id)}`, { headers: { 'X-Report-Token': token } })
export const radar = () => call<Radar>('/v1/radar')
export const pasteSms = (text: string) => call<SmsResult>('/v1/sms', { method: 'POST', body: JSON.stringify({ text }) })

export function previewSrc(path: string): string {
  return path.startsWith('/v1/') ? `/api${path}` : path
}
