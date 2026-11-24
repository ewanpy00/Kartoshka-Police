// The one fetch wrapper (docs/admin-dashboard.md, "Auth"): every console call goes through it and carries
// the write token. The console stays on 127.0.0.1 because the token ships in the bundle.
const token = import.meta.env.VITE_CORE_WRITE_TOKEN as string | undefined

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers)
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }
  return fetch(`/api${path}`, { ...init, headers })
}

async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`
    try {
      const body = await response.json()
      if (typeof body.detail === 'string') message = body.detail
      else if (Array.isArray(body.detail)) message = body.detail.map((d: { msg: string }) => d.msg).join('; ')
    } catch {
      /* not JSON */
    }
    throw new ApiError(response.status, message)
  }
  return response.json() as Promise<T>
}

export async function get<T>(path: string, params: Record<string, string | number | boolean | undefined | null> = {}): Promise<T> {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') query.set(key, String(value))
  }
  const suffix = query.toString() ? `?${query}` : ''
  return parse<T>(await apiFetch(`${path}${suffix}`))
}

export async function post<T>(path: string, body: unknown = {}): Promise<T> {
  return parse<T>(await apiFetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }))
}

/** Downloads a binary route (pack zip) through the wrapper, so the token is sent. */
export async function download(path: string, fallbackName: string): Promise<Record<string, string>> {
  const response = await apiFetch(path)
  if (!response.ok) throw new ApiError(response.status, `${response.status} ${response.statusText}`)
  const blob = await response.blob()
  const disposition = response.headers.get('Content-Disposition') ?? ''
  const name = /filename="([^"]+)"/.exec(disposition)?.[1] ?? fallbackName
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = name
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 10_000)
  const headers: Record<string, string> = {}
  response.headers.forEach((value, key) => { headers[key] = value })
  return headers
}

export function evidenceUrl(evidenceId: string, kind: 'pdf' | 'json'): string {
  return `/api/v1/evidence/${encodeURIComponent(evidenceId)}.${kind}`
}

export function previewUrl(evidenceId: string): string {
  return `/api/v1/preview/${encodeURIComponent(evidenceId)}.png`
}

export interface LiveEvent {
  type: string
  [key: string]: unknown
}

type Listener = (event: LiveEvent) => void
const listeners = new Set<Listener>()
let socket: WebSocket | null = null
let retry = 1000

function connect(): void {
  if (!token) return
  const scheme = location.protocol === 'https:' ? 'wss' : 'ws'
  socket = new WebSocket(`${scheme}://${location.host}/api/v1/events?token=${encodeURIComponent(token)}`)
  socket.onopen = () => { retry = 1000 }
  socket.onmessage = (message) => {
    try {
      const event = JSON.parse(message.data) as LiveEvent
      listeners.forEach((listener) => listener(event))
    } catch {
      /* ignore malformed frames */
    }
  }
  socket.onclose = () => {
    socket = null
    if (listeners.size) setTimeout(connect, retry)
    retry = Math.min(retry * 2, 30_000)
  }
}

/** Live events from core (`WS /v1/events`); returns the unsubscribe function. */
export function onEvent(listener: Listener): () => void {
  listeners.add(listener)
  if (!socket) connect()
  return () => {
    listeners.delete(listener)
    if (!listeners.size && socket) socket.close()
  }
}
