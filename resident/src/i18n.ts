// Arabic first (ARCHITECTURE.md section 3), English on a tap.
import { ref, watchEffect } from 'vue'

export type Lang = 'ar' | 'en'
function initial(): Lang {
  try {
    const saved = localStorage.getItem('kp.lang')
    if (saved === 'en' || saved === 'ar') return saved
  } catch {
    /* ignore */
  }
  return 'ar'
}
export const lang = ref<Lang>(initial())
watchEffect(() => {
  document.documentElement.lang = lang.value
  document.documentElement.dir = lang.value === 'ar' ? 'rtl' : 'ltr'
  try {
    localStorage.setItem('kp.lang', lang.value)
  } catch {
    /* ignore */
  }
})

/** Pick the text for the current language. */
export function tr(en: string, ar: string): string {
  return lang.value === 'ar' ? ar : en
}

export const SOURCE_NAMES: Record<string, [string, string]> = {
  allowlist: ['Official list', 'القائمة الرسمية'],
  police_blocklist: ['Police-confirmed list', 'قائمة الشرطة المؤكدة'],
  gsb: ['Google Safe Browsing', 'التصفح الآمن من Google'],
  virustotal: ['VirusTotal', 'VirusTotal'],
  feeds: ['Phishing feeds', 'قوائم التصيّد'],
  rdap: ['Domain age', 'عمر النطاق'],
  ct: ['First certificate (CT)', 'أول شهادة أمان'],
  campaign: ['Campaign link', 'ارتباط بحملة'],
  sandbox: ['Safe preview', 'المعاينة الآمنة'],
  ai: ['AI explanation', 'شرح الذكاء الاصطناعي'],
}

export const ASKS: Record<string, [string, string]> = {
  otp: ['one-time code', 'رمز التحقق'], card: ['card number', 'رقم البطاقة'], cvv: ['card security code', 'رمز أمان البطاقة'],
  emirates_id: ['Emirates ID', 'الهوية الإماراتية'], iban: ['IBAN', 'رقم الآيبان'], uaepass: ['UAE PASS login', 'بيانات الهوية الرقمية'],
  password: ['password', 'كلمة المرور'],
}
