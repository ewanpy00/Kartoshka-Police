export function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers)
  const token = import.meta.env.VITE_CORE_WRITE_TOKEN
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }
  return fetch(`/api${path}`, { ...init, headers })
}
