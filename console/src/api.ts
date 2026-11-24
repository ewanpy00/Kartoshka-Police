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

export async function apiJson<T>(path: string): Promise<T> {
  const response = await apiFetch(path)
  if (!response.ok) throw await failure(response)
  return response.json()
}

export async function postJson<T>(path: string, body: object): Promise<T> {
  const response = await apiFetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) throw await failure(response)
  return response.json()
}

export async function fetchBlob(path: string): Promise<Blob> {
  const response = await apiFetch(path)
  if (!response.ok) throw await failure(response)
  return response.blob()
}

export async function download(path: string, filename: string): Promise<void> {
  const url = URL.createObjectURL(await fetchBlob(path))
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}
