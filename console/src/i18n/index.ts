// Two languages; Arabic switches the whole console to RTL (ARCHITECTURE.md section 5).
import { ref, watchEffect } from 'vue'
import { ar } from './ar'
import { en, type MessageKey } from './en'

export type Lang = 'en' | 'ar'
const KEY = 'kp.console.lang'

function initial(): Lang {
  try {
    return localStorage.getItem(KEY) === 'ar' ? 'ar' : 'en'
  } catch {
    return 'en'
  }
}

export const lang = ref<Lang>(initial())

watchEffect(() => {
  document.documentElement.lang = lang.value
  document.documentElement.dir = lang.value === 'ar' ? 'rtl' : 'ltr'
  try {
    localStorage.setItem(KEY, lang.value)
  } catch {
    /* ignore */
  }
})

export function t(key: MessageKey): string {
  // Keys built at run time (status names) may be missing: the key itself comes back, and callers fall back.
  return (lang.value === 'ar' ? ar[key] : undefined) ?? en[key] ?? key
}

export function toggleLang(): void {
  lang.value = lang.value === 'ar' ? 'en' : 'ar'
}
