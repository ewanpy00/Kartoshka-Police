import { adaptRequest, adaptResponse, pagedKey } from './adapt'
import { demoRunning } from './demo'
import { DEMO_WAIT_MS, demoBlob, demoFallback, demoFill } from './demoData'

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly body: unknown,
  ) {
    super(`Request failed with status ${status}`)
  }
}

export function apiToken(): string {
  return import.meta.env.VITE_CORE_WRITE_TOKEN ?? ''
}

export function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers)
  const token = apiToken()
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }
  return fetch(`/api${path}`, { ...init, headers })
}

async function failure(response: Response): Promise<ApiError> {
  const body: unknown = await response.json().catch(() => null)
  return new ApiError(response.status, body)
}

const MAX_PAGES = 20

/** Every page of a cursor-paginated route, rows concatenated, the last page's other fields kept. */
async function allPages(path: string, key: string): Promise<unknown> {
  let merged: Record<string, unknown> | null = null
  let cursor: string | null = null
  for (let page = 0; page < MAX_PAGES; page++) {
    // The demo shows the first page only: a long list (hundreds of open cases) would keep a page empty for many
    // seconds, and a load already running when the demo starts stops here so it does not hold the connections.
    if (page > 0 && demoRunning.value) break
    const url: string = cursor === null ? path : `${path}${path.includes('?') ? '&' : '?'}cursor=${encodeURIComponent(cursor)}`
    const response = await apiFetch(url)
    if (!response.ok) throw await failure(response)
    const body = (await response.json()) as Record<string, unknown>
    merged = merged ? { ...body, [key]: [...(merged[key] as unknown[]), ...((body[key] as unknown[]) ?? [])] } : body
    const next = body.next_cursor
    if (next === null || next === undefined) break
    cursor = String(next)
  }
  return merged
}

// Views ask in main's vocabulary; adapt.ts turns the backend's answers into main's shapes (types.ts).
export async function apiJson<T>(path: string): Promise<T> {
  const real = loadJson<T>(path)
  const sample = demoRunning.value ? demoFallback(path) : null
  if (sample === null) return real
  // During the demo a slow or failing backend must not leave a page on "Loading" or an error: after a short
  // wait, or as soon as the real request fails, show the sample.
  return Promise.race([
    real.catch(() => sample as T),
    new Promise<T>((resolve) => setTimeout(() => resolve(sample as T), DEMO_WAIT_MS)),
  ])
}

async function loadJson<T>(path: string): Promise<T> {
  const key = pagedKey(path)
  if (key) return demoFill(path, adaptResponse(path, await allPages(path, key)) as T)
  const response = await apiFetch(path)
  if (!response.ok) throw await failure(response)
  return demoFill(path, adaptResponse(path, await response.json()) as T)
}

export async function postJson<T>(path: string, body: object): Promise<T> {
  const response = await apiFetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(adaptRequest(path, body)),
  })
  if (!response.ok) throw await failure(response)
  return adaptResponse(path, await response.json(), 'POST') as T
}

export async function fetchBlob(path: string): Promise<Blob> {
  const sample = demoBlob(path)
  if (sample) return sample
  const response = await apiFetch(path)
  if (!response.ok) throw await failure(response)
  return response.blob()
}

export async function download(path: string, filename: string): Promise<void> {
  const url = URL.createObjectURL(await fetchBlob(path))
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.append(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 10_000)
}

export function errorText(error: unknown): string {
  if (error instanceof ApiError) {
    const detail = (error.body as { detail?: unknown } | null)?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return detail.map((item) => item?.msg ?? String(item)).join('; ')
    return error.message
  }
  return error instanceof Error ? error.message : String(error)
}
