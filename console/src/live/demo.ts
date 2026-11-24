// A scripted scenario for rehearsals and pitches without a running stack (`/live?demo=1`).
// Every name below is invented; the wall shows a "DEMO DATA" tag whenever this source is active.
// Reason codes, weights and source ids match core/app/verdict/reasons.py and bands.py.
import type { LiveEvent } from '../api'
import type { CaseDetail, Reason, Source } from '../types'
import type { LiveSource, Totals } from './source'

interface Scripted {
  domain: string
  brand: string
  brandId: string
  url: string
  fast: Reason[]
  deep: Reason[]
  fastSources: Source[]
  deepSources: Source[]
  title: string
  asksFor: string[]
  visual: number | null
  ai: string
  decision: 'confirm' | 'reject'
  campaign: string | null
}

const r = (code: string, weight: number, source: string, en: string, ar?: string): Reason => ({ code, weight, source, en, ar })
const s = (id: string, status: string, detail?: string): Source => ({ id, status, detail })

const SCRIPT: Scripted[] = [
  {
    domain: 'uaepass-verify.top', brand: 'UAE PASS', brandId: 'uaepass', url: 'https://uaepass-verify.top/login',
    fast: [
      r('BRAND_IN_DOMAIN', 40, 'kartoshka', "Domain uses 'uaepass' but is not an official UAE PASS domain", "النطاق يستخدم اسم 'uaepass' لكنه ليس نطاقًا رسميًا للهوية الرقمية"),
      r('DOMAIN_AGE', 25, 'rdap', 'Registered 2 days ago', 'تم تسجيله قبل يومين'),
    ],
    deep: [
      r('VISUAL_MATCH', 35, 'sandbox', 'Page looks 91% like the official UAE PASS page', 'الصفحة تشبه صفحة الهوية الرقمية الرسمية بنسبة 91٪'),
      r('ASKS_OTP', 35, 'sandbox', 'Page asks for a one-time code (OTP)', 'الصفحة تطلب رمز التحقق لمرة واحدة (OTP)'),
      r('AI_ASSESSMENT', 0, 'ai', 'AI review: login page imitating UAE PASS that collects the SMS code', 'مراجعة الذكاء الاصطناعي: صفحة دخول تقلّد الهوية الرقمية وتجمع رمز الرسالة'),
    ],
    fastSources: [s('allowlist', 'clean'), s('police_blocklist', 'clean'), s('gsb', 'unknown', 'timeout'), s('virustotal', 'hit', '7/94 engines'),
      s('feeds', 'clean'), s('rdap', 'hit', 'registered 2 days ago'), s('ct', 'hit', 'first certificate 26 h ago'), s('campaign', 'hit', 'cmp_17, 14 sites')],
    deepSources: [s('sandbox', 'hit', 'asks for OTP'), s('ai', 'hit', 'high')],
    title: 'Sign in', asksFor: ['uaepass', 'otp'], visual: 0.91,
    ai: 'Login page imitating UAE PASS. It asks for the national ID and then the one-time SMS code, and posts both to an unrelated host.',
    decision: 'confirm', campaign: 'cmp_17',
  },
  {
    domain: 'tamm-fines-pay.com', brand: 'TAMM', brandId: 'tamm', url: 'https://tamm-fines-pay.com/pay?ref=AD-55120',
    fast: [
      r('BRAND_IN_DOMAIN', 40, 'kartoshka', "Domain uses 'tamm' but is not an official TAMM domain", "النطاق يستخدم اسم 'tamm' لكنه ليس نطاقًا رسميًا لتم"),
      r('ACTION_WORDS', 10, 'kartoshka', 'Address contains pressure words: fines, pay', 'العنوان يحتوي على كلمات ضغط: fines, pay'),
    ],
    deep: [
      r('ASKS_CARD', 35, 'sandbox', 'Page asks for a card number', 'الصفحة تطلب رقم البطاقة'),
      r('AI_ASSESSMENT', 0, 'ai', 'AI review: fake traffic-fine payment page', 'مراجعة الذكاء الاصطناعي: صفحة دفع مخالفات مزيفة'),
    ],
    fastSources: [s('allowlist', 'clean'), s('police_blocklist', 'clean'), s('gsb', 'clean'), s('virustotal', 'clean', '0/94 engines'),
      s('feeds', 'clean'), s('rdap', 'unknown', 'rate limited'), s('ct', 'hit', 'first certificate 3 h ago'), s('campaign', 'clean')],
    deepSources: [s('sandbox', 'hit', 'asks for card'), s('ai', 'hit', 'high')],
    title: 'Pay your traffic fine', asksFor: ['card'], visual: null,
    ai: 'Traffic-fine payment page with a countdown. Takes the card number on a page that is not a government domain.',
    decision: 'confirm', campaign: null,
  },
  {
    domain: 'uаepass-login.com', brand: 'UAE PASS', brandId: 'uaepass', url: 'https://uаepass-login.com/',
    fast: [
      r('HOMOGLYPH', 35, 'kartoshka', "Domain uses look-alike characters to imitate 'uaepass'", "النطاق يستخدم أحرفًا متشابهة لتقليد 'uaepass'"),
      r('MIXED_SCRIPTS', 20, 'kartoshka', 'Domain mixes alphabets (Latin, Cyrillic)', 'النطاق يخلط بين أبجديات مختلفة (Latin, Cyrillic)'),
      r('FRESH_CERT', 10, 'ct', 'First TLS certificate issued 5 hours ago', 'أول شهادة صدرت قبل 5 ساعات'),
    ],
    deep: [
      r('BRAND_MISMATCH', 30, 'sandbox', "Page shows UAE PASS branding on a domain that is not UAE PASS's", 'الصفحة تعرض علامة الهوية الرقمية على نطاق لا يتبع لها'),
      r('AI_ASSESSMENT', 0, 'ai', 'AI review: credential phishing with a look-alike address', 'مراجعة الذكاء الاصطناعي: تصيّد بيانات دخول بعنوان مشابه'),
    ],
    fastSources: [s('allowlist', 'clean'), s('police_blocklist', 'clean'), s('gsb', 'clean'), s('virustotal', 'clean', '0/94 engines'),
      s('feeds', 'clean'), s('rdap', 'hit', 'registered yesterday'), s('ct', 'hit', 'first certificate 5 h ago'), s('campaign', 'clean')],
    deepSources: [s('sandbox', 'hit', 'brand on foreign domain'), s('ai', 'hit', 'high')],
    title: 'Sign in', asksFor: ['password'], visual: null,
    ai: 'The second letter is Cyrillic "а" (U+0430), so the address reads as uaepass but is a different domain.',
    decision: 'confirm', campaign: null,
  },
  {
    domain: 'rta-parking-refund.info', brand: 'RTA', brandId: 'rta', url: 'https://rta-parking-refund.info/',
    fast: [r('BRAND_IN_DOMAIN', 40, 'kartoshka', "Domain uses 'rta' but is not an official RTA domain", "النطاق يستخدم اسم 'rta' لكنه ليس نطاقًا رسميًا لهيئة الطرق")],
    deep: [r('PARKED', 5, 'sandbox', 'Page is parked or empty; kept on the watchlist', 'الصفحة متوقفة أو فارغة؛ تبقى في قائمة المراقبة')],
    fastSources: [s('allowlist', 'clean'), s('police_blocklist', 'clean'), s('gsb', 'clean'), s('virustotal', 'clean', '0/94 engines'),
      s('feeds', 'clean'), s('rdap', 'clean', 'registered 3 years ago'), s('ct', 'clean'), s('campaign', 'clean')],
    deepSources: [s('sandbox', 'clean', 'parked page'), s('ai', 'skipped')],
    title: 'Domain parked', asksFor: [], visual: null,
    ai: '',
    decision: 'reject', campaign: null,
  },
]

const NOISE: [string, string | null][] = [
  ['tamm-pay-fine.com', 'tamm'], ['rta-fines-ae.top', 'rta'], ['emiratesid-renew.net', 'icp'], ['adcb-secure-login.xyz', 'adcb'],
  ['dewa-refund.info', 'dewa'], ['etisalat-rewards.top', 'etisalat'], ['du-bill-pay.com', 'du'], ['aramex-redelivery.top', 'aramex'],
  ['emiratespost-parcel.com', 'emiratespost'], ['enbd-verify-otp.top', 'enbd'], ['mohre-visa-check.com', 'mohre'], ['salik-topup.top', 'salik'],
  ['dwu6.top', null], ['k2-pay-ae.shop', null], ['icp-uae-renew.com', 'icp'], ['dubaipolice-fine.top', 'dubaipolice'],
]
const SOURCES = ['ct', 'ct', 'ct', 'nrd', 'feed']

function score(reasons: Reason[]): number {
  return Math.max(0, Math.min(100, reasons.reduce((total, reason) => total + (reason.weight ?? 0), 0)))
}
function band(value: number): string {
  return value > 70 ? 'block' : value >= 30 ? 'warn' : 'allow'
}
function defang(value: string): string {
  return value.replace(/^https:\/\//, 'hxxps://').replace(/\./g, '[.]')
}

function detail(item: Scripted, deep: boolean, checkId: string): CaseDetail {
  const reasons = deep ? [...item.fast, ...item.deep] : item.fast
  const value = score(reasons)
  const now = new Date().toISOString()
  return {
    domain: item.domain, display: defang(item.domain), status: null, status_source: null,
    latest: {
      check_id: checkId, url: item.url, display_url: defang(item.url), display_final_url: null,
      verdict: band(value), score: value, stage: deep ? 'deep' : 'fast', brand: item.brand, brand_id: item.brandId, reasons,
      sources: deep ? [...item.fastSources, ...item.deepSources.map((x) => (x.id === 'ai' && item.ai ? { ...x, detail: item.ai } : x))] : [...item.fastSources, s('sandbox', 'unknown', 'running'), s('ai', 'unknown', 'running')],
      features: {}, deep_status: deep ? 'done' : 'running', evidence_id: null, preview: null, created_at: now,
      safe_action: item.decision === 'confirm' ? { label_en: `Use the official ${item.brand} app or website`, label_ar: 'استخدم التطبيق أو الموقع الرسمي' } : null,
    },
    page: deep ? { title: item.title, status: 200, lang: 'en', asks_for: item.asksFor, phones: [], payment_hosts: [] } : null,
    infra: null,
    visual: deep && item.visual ? { brand_id: item.brandId, similarity: item.visual } : null,
    kit: null, discovery: [], reports: { count: 0, notes: [] }, hits: {}, campaign: null, watchlist: null, reviews: [], history: [],
  }
}

export function createDemoSource(): LiveSource {
  const listeners = new Set<(event: LiveEvent) => void>()
  const state = new Map<string, boolean>()
  const checks = new Map<string, string>()
  const timers = new Set<number>()
  let seq = 0

  const emit = (event: LiveEvent) => listeners.forEach((listener) => listener({ at: new Date().toISOString(), ...event }))
  const at = (ms: number, fn: () => void) => {
    const id = window.setTimeout(() => { timers.delete(id); fn() }, ms)
    timers.add(id)
  }

  function noise() {
    const [domain, brand] = NOISE[Math.floor(Math.random() * NOISE.length)]
    emit({ type: 'hunter.candidate', source: SOURCES[Math.floor(Math.random() * SOURCES.length)], domain, brand_id: brand, first_seen: new Date().toISOString() })
    at(1400 + Math.random() * 1600, noise)
  }

  function verdict(item: Scripted, deep: boolean) {
    const check = checks.get(item.domain) ?? `c_demo_${++seq}`
    checks.set(item.domain, check)
    state.set(item.domain, deep)
    const d = detail(item, deep, check)
    emit({ type: 'check.verdict', check_id: check, domain: item.domain, host: item.domain, verdict: d.latest!.verdict,
      score: d.latest!.score, stage: deep ? 'deep' : 'fast', source: 'ct', brand: item.brand })
  }

  function round() {
    state.clear()
    checks.clear()
    let t = 600
    SCRIPT.forEach((item, i) => {
      at(t, () => emit({ type: 'hunter.candidate', source: 'ct', domain: item.domain, brand_id: item.brandId, first_seen: new Date().toISOString() }))
      at(t + 1200, () => verdict(item, false))
      at(t + 4800, () => verdict(item, true))
      at(t + 12000, () => emit({ type: 'case.reviewed', domain: item.domain, decision: item.decision, reviewer: 'Demo Officer' }))
      if (item.campaign) at(t + 12800, () => emit({ type: 'campaign.new_domain', campaign_id: item.campaign, domain: item.domain }))
      if (i === 1) at(t + 6000, () => emit({ type: 'brand.spike', brand_id: 'tamm', count: 9 }))
      if (i === 2) at(t + 9000, () => emit({ type: 'takedown.offline', domain: 'tamm-pay-fine.com', state: 'closed' }))
      t += 14500
    })
    at(t + 1500, round)
  }

  return {
    demo: true,
    subscribe(listener) {
      listeners.add(listener)
      if (listeners.size === 1) {
        at(200, () => emit({ type: 'hello' }))
        at(900, noise)
        round()
      }
      return () => {
        listeners.delete(listener)
        if (!listeners.size) {
          timers.forEach((timer) => window.clearTimeout(timer))
          timers.clear()
        }
      }
    },
    async caseDetail(domain) {
      const item = SCRIPT.find((entry) => entry.domain === domain)
      if (!item) return null
      return detail(item, state.get(domain) ?? false, checks.get(domain) ?? 'c_demo')
    },
    async totals(): Promise<Totals> {
      return { candidates: 1284, threats: 211, confirmed: 37, blocklist: 412 }
    },
    async replay() {
      return []
    },
    screenshot() {
      return null
    },
  }
}
