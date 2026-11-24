import { ref, type Ref } from 'vue'
import { apiJson } from './api'
import type { Health } from './types'

const REFRESH_MS = 30_000

const health = ref<Health | null>(null)
const reachable = ref<boolean | null>(null)
let timer: ReturnType<typeof setInterval> | null = null
let latest = 0

export function useHealth() {
  return { health, reachable } as { health: Ref<Health | null>; reachable: Ref<boolean | null> }
}

export async function refreshHealth(): Promise<void> {
  const mine = ++latest
  try {
    const loaded = await apiJson<Health>('/v1/admin/health')
    if (mine !== latest) return
    health.value = loaded
    reachable.value = true
  } catch {
    if (mine !== latest) return
    health.value = null
    reachable.value = false
  }
}

export function startHealth(): void {
  if (timer !== null) return
  void refreshHealth()
  timer = setInterval(() => void refreshHealth(), REFRESH_MS)
}

export function stopHealth(): void {
  if (timer !== null) clearInterval(timer)
  timer = null
  latest++
}

export function _resetHealthForTest(): void {
  stopHealth()
  health.value = null
  reachable.value = null
}
