// Mock UAE PASS sign-in (ARCHITECTURE.md section 5): a local demo session only. No OAuth, no client id,
// no call to any UAE PASS endpoint. The reviewer name is sent in each write body.
import { ref } from 'vue'

export interface Session {
  name: string
  role: 'officer'
  signedInAt: string
}

const KEY = 'kp.console.session'

function load(): Session | null {
  try {
    const raw = sessionStorage.getItem(KEY)
    return raw ? (JSON.parse(raw) as Session) : null
  } catch {
    return null
  }
}

export const session = ref<Session | null>(load())

export function signIn(name = 'Demo Officer'): void {
  session.value = { name, role: 'officer', signedInAt: new Date().toISOString() }
  try {
    sessionStorage.setItem(KEY, JSON.stringify(session.value))
  } catch {
    /* private mode: the session lasts until reload */
  }
}

export function signOut(): void {
  session.value = null
  try {
    sessionStorage.removeItem(KEY)
  } catch {
    /* ignore */
  }
}

export function reviewer(): string {
  return session.value?.name ?? 'Demo Officer'
}
