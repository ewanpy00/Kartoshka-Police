import { ref, type Ref } from 'vue'
import { apiJson } from './api'
import type { Health } from './types'

const REFRESH_MS = 30_000

const health = ref<Health | null>(null)
const reachable = ref<boolean | null>(null)
let timer: ReturnType<typeof setInterval> | null = null

export function useHealth() {
  return { health, reachable } as { health: Ref<Health | null>; reachable: Ref<boolean | null> }
}

export async function refreshHealth(): Promise<void> {
  try {
    health.value = await apiJson<Health>('/v1/admin/health')
    reachable.value = true
  } catch {
    health.value = null
    reachable.value = false
  }
}

export function startHealth(): void {
  if (timer !== null) return
  void refreshHealth()
  timer = setInterval(() => void refreshHealth(), REFRESH_MS)
}

export function _resetHealthForTest(): void {
  if (timer !== null) clearInterval(timer)
  timer = null
  health.value = null
  reachable.value = null
}
