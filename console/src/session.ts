import { ref } from 'vue'
import { API_PREFIX } from './apiPrefix'
import { t } from './i18n'

export interface Officer {
  name: string
  role: 'officer'
}

const KEY = 'officer'
const CODE_KEY = 'access_code'

function load(): Officer | null {
  try {
    const raw = sessionStorage.getItem(KEY)
    return raw && sessionStorage.getItem(CODE_KEY) ? (JSON.parse(raw) as Officer) : null
  } catch {
    return null
  }
}

function loadCode(): string {
  try {
    return sessionStorage.getItem(CODE_KEY) ?? ''
  } catch {
    return ''
  }
}

export const officer = ref<Officer | null>(load())
const code = ref(loadCode())

/** The access code the officer signed in with; sent as the bearer token. */
export function accessCode(): string {
  return code.value
}

/** Checks the code against core. Resolves to null when accepted, else the message to show. */
export async function signIn(entered: string): Promise<string | null> {
  const candidate = entered.trim()
  if (!candidate) return t('signInEmpty')
  let response: Response
  try {
    response = await fetch(`${API_PREFIX}/v1/admin/health`, { headers: { Authorization: `Bearer ${candidate}` } })
  } catch {
    return t('signInNetwork')
  }
  if (response.status === 401) return t('signInRejected')
  if (response.status === 429) return t('signInThrottled')
  if (!response.ok) return t('signInNetwork')
  code.value = candidate
  officer.value = { name: 'Demo Officer', role: 'officer' }
  sessionStorage.setItem(CODE_KEY, candidate)
  sessionStorage.setItem(KEY, JSON.stringify(officer.value))
  return null
}

export function signOut(): void {
  officer.value = null
  code.value = ''
  sessionStorage.removeItem(KEY)
  sessionStorage.removeItem(CODE_KEY)
}

export function officerName(): string {
  return officer.value?.name ?? 'Demo Officer'
}
