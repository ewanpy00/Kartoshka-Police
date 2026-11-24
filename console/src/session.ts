import { ref } from 'vue'

export interface Officer {
  name: string
  role: 'officer'
}

const KEY = 'officer'

function load(): Officer | null {
  try {
    const raw = sessionStorage.getItem(KEY)
    return raw ? (JSON.parse(raw) as Officer) : null
  } catch {
    return null
  }
}

export const officer = ref<Officer | null>(load())

export function signIn(): void {
  officer.value = { name: 'Demo Officer', role: 'officer' }
  sessionStorage.setItem(KEY, JSON.stringify(officer.value))
}

export function signOut(): void {
  officer.value = null
  sessionStorage.removeItem(KEY)
}

export function officerName(): string {
  return officer.value?.name ?? 'Demo Officer'
}
