// Demo data: open any page with ?demo=1 (or build with VITE_DEMO=1) and every API call is answered from the
// fixtures below instead of core, so each screen can be seen filled in, with no core running. ?demo=0 turns it
// off again. Demo reports live under their own storage key, so the device's real reports are never touched.
// Reports sent in demo mode move through the stages on their own (checked after ~15 s, police review after
// ~40 s, confirmed after ~90 s), which shows the tracker updating live.
import type { Radar, ReportStatus, SmsResult, Source, Step, Verdict } from './api'

const FLAG = 'kp.demo'

function initial(): boolean {
  if (import.meta.env.VITE_DEMO === '1') return true
  const param = new URLSearchParams(location.search).get('demo')
  try {
    if (param === '1') localStorage.setItem(FLAG, '1')
    if (param === '0') localStorage.removeItem(FLAG)
    return localStorage.getItem(FLAG) === '1'
  } catch {
    return param === '1'
  }
}

export const demo = initial()
if (demo) document.documentElement.classList.add('demo')

// --- time helpers -----------------------------------------------------------------------------------

const MIN = 60_000
const HOUR = 60 * MIN
const DAY = 24 * HOUR
const ago = (ms: number) => new Date(Date.now() - ms).toISOString()
const at = (base: number, ms: number) => new Date(base + ms).toISOString()

// --- link checks ------------------------------------------------------------------------------------

interface Profile { verdict: Verdict['verdict']; score: number; brand: string | null; reasons: [string, string, string][]; sources: Source[]; asks: string[] }

const SAFE: Record<string, { label_en: string; label_ar: string; url: string }> = {
  TAMM: { label_en: 'Pay fines on TAMM', label_ar: 'ادفع المخالفات عبر تم', url: 'https://www.tamm.abudhabi/' },
  RTA: { label_en: 'Open the RTA app', label_ar: 'افتح تطبيق هيئة الطرق', url: 'https://www.rta.ae/' },
  'UAE PASS': { label_en: 'Sign in on UAE PASS', label_ar: 'سجّل الدخول عبر الهوية الرقمية', url: 'https://uaepass.ae/' },
  'Emirates Post': { label_en: 'Track a parcel on Emirates Post', label_ar: 'تتبّع شحنتك عبر بريد الإمارات', url: 'https://www.emiratespost.ae/' },
  Salik: { label_en: 'Top up on Salik', label_ar: 'اشحن رصيد سالك', url: 'https://www.salik.ae/' },
  Etisalat: { label_en: 'Pay your bill on e&', label_ar: 'ادفع فاتورتك عبر e&', url: 'https://www.etisalat.ae/' },
}

const OFFICIAL = ['tamm.abudhabi', 'rta.ae', 'uaepass.ae', 'emiratespost.ae', 'salik.ae', 'etisalat.ae', 'dubaipolice.gov.ae', 'adpolice.gov.ae']

const BRAND_WORDS: [RegExp, string][] = [
  [/tamm/, 'TAMM'], [/rta|fines?|traffic/, 'RTA'], [/uae-?pass/, 'UAE PASS'], [/post|parcel|deliver/, 'Emirates Post'],
  [/salik|toll/, 'Salik'], [/etisalat|e-and|eand/, 'Etisalat'],
]

const src = (id: string, status: Source['status'], detail: string | null = null): Source => ({ id, status, detail })

function profile(url: string): Profile {
  let host = url
  try {
    host = new URL(url).hostname.toLowerCase()
  } catch {
    /* keep the raw text */
  }
  if (OFFICIAL.some((d) => host === d || host.endsWith(`.${d}`))) {
    return {
      verdict: 'allow', score: 3, brand: null, asks: [],
      reasons: [['official_domain', 'This is an official government or company address.', 'هذا عنوان رسمي لجهة حكومية أو شركة.']],
      sources: [src('allowlist', 'hit', 'official domain'), src('police_blocklist', 'clean'), src('gsb', 'clean'), src('virustotal', 'clean'),
        src('feeds', 'clean'), src('rdap', 'clean', 'registered 2009'), src('ct', 'clean'), src('campaign', 'clean'), src('sandbox', 'skipped'), src('ai', 'skipped')],
    }
  }
  const brand = BRAND_WORDS.find(([re]) => re.test(host))?.[1] ?? null
  const cheapTld = /\.(top|xyz|shop|info|click|live|online|cc|icu|sbs)$/.test(host)
  if (brand && (cheapTld || host.includes('-'))) {
    return {
      verdict: 'block', score: 94, brand, asks: ['card', 'cvv', 'otp'],
      reasons: [
        ['brand_impersonation', `The address imitates ${brand} but is not theirs.`, `العنوان يقلّد ${brand} لكنه ليس تابعًا لها.`],
        ['young_domain', 'The site was registered 2 days ago.', 'تم تسجيل الموقع قبل يومين.'],
        ['asks_payment', 'The page asks for your card number and a one-time code.', 'تطلب الصفحة رقم بطاقتك ورمز التحقق.'],
        ['campaign', 'It belongs to a campaign of 41 similar links sent by SMS this week.', 'ينتمي إلى حملة من 41 رابطًا مشابهًا أُرسلت عبر الرسائل هذا الأسبوع.'],
      ],
      sources: [src('allowlist', 'clean'), src('police_blocklist', 'hit', 'confirmed by police'), src('gsb', 'hit', 'SOCIAL_ENGINEERING'),
        src('virustotal', 'hit', '9 / 94 engines'), src('feeds', 'hit', 'OpenPhish'), src('rdap', 'hit', 'registered 2 days ago'),
        src('ct', 'hit', 'first certificate 2 days ago'), src('campaign', 'hit', '41 links'), src('sandbox', 'hit', 'card form'), src('ai', 'hit')],
    }
  }
  if (brand || cheapTld) {
    return {
      verdict: 'warn', score: 58, brand, asks: ['password'],
      reasons: [
        ['young_domain', 'The site is less than a month old.', 'عمر الموقع أقل من شهر.'],
        ['lookalike', 'The address looks like a known service, so check it carefully.', 'العنوان يشبه خدمة معروفة، فتحقّق منه جيدًا.'],
      ],
      sources: [src('allowlist', 'clean'), src('police_blocklist', 'clean'), src('gsb', 'clean'), src('virustotal', 'hit', '1 / 94 engines'),
        src('feeds', 'clean'), src('rdap', 'hit', 'registered 19 days ago'), src('ct', 'clean'), src('campaign', 'unknown'), src('sandbox', 'unknown'), src('ai', 'clean')],
    }
  }
  return {
    verdict: 'allow', score: 12, brand: null, asks: [],
    reasons: [['no_signals', 'No warning signs found. Still, never share codes you receive by SMS.', 'لم نجد علامات تحذير. ومع ذلك لا تشارك رموز التحقق أبدًا.']],
    sources: [src('allowlist', 'unknown'), src('police_blocklist', 'clean'), src('gsb', 'clean'), src('virustotal', 'clean'),
      src('feeds', 'clean'), src('rdap', 'clean', 'registered 2016'), src('ct', 'clean'), src('campaign', 'clean'), src('sandbox', 'skipped'), src('ai', 'clean')],
  }
}

const SHOT = 'data:image/svg+xml;utf8,' + encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="360" height="640" viewBox="0 0 360 640">
<rect width="360" height="640" fill="#f4f5f7"/><rect width="360" height="64" fill="#1f3a5f"/>
<text x="20" y="40" font-family="sans-serif" font-size="18" fill="#fff">Fine payment</text>
<text x="20" y="110" font-family="sans-serif" font-size="20" font-weight="700" fill="#1b1f29">Unpaid fine: AED 150</text>
<text x="20" y="138" font-family="sans-serif" font-size="13" fill="#6b7280">Pay today to avoid a penalty</text>
<g font-family="sans-serif" font-size="12" fill="#6b7280"><text x="20" y="186">Card number</text><text x="20" y="256">Expiry</text>
<text x="190" y="256">CVV</text><text x="20" y="326">Code sent by SMS</text></g>
<g fill="#fff" stroke="#cfd4dc"><rect x="20" y="194" width="320" height="40" rx="6"/><rect x="20" y="264" width="150" height="40" rx="6"/>
<rect x="190" y="264" width="150" height="40" rx="6"/><rect x="20" y="334" width="320" height="40" rx="6"/></g>
<rect x="20" y="404" width="320" height="48" rx="8" fill="#c0392b"/><text x="180" y="434" text-anchor="middle" font-family="sans-serif" font-size="16" fill="#fff">Pay now</text>
</svg>`)

const checks = new Map<string, Verdict>()
let counter = 0

function verdictFor(url: string, previewed = false): Verdict {
  const p = profile(url)
  counter += 1
  const id = `demo-chk-${Date.now().toString(36)}-${counter}`
  const v: Verdict = {
    check_id: id, url, final_url: url, verdict: p.verdict, score: p.score, stage: 'fast', brand: p.brand,
    safe_action: p.brand && p.verdict !== 'allow' ? SAFE[p.brand] ?? null : null,
    reasons: p.reasons.map(([code, en, ar]) => ({ code, weight: null, source: 'demo', en, ar })),
    sources: p.sources,
    preview: previewed ? { screenshot: SHOT, asks_for: p.asks, title: 'Fine payment' } : null,
    deep_status: p.verdict === 'allow' ? null : 'queued',
    evidence_id: p.verdict === 'block' ? `EV-${id.slice(-6).toUpperCase()}` : null,
  }
  checks.set(id, v)
  return v
}

/** A queued deep check finishes on the second poll, with a screenshot of the page. */
function followCheck(id: string): Verdict {
  const v = checks.get(id)
  if (!v) throw new Error('404')
  if (v.deep_status === 'queued') v.deep_status = 'running'
  else if (v.deep_status === 'running') {
    v.deep_status = 'done'
    v.stage = 'deep'
    v.preview = { screenshot: SHOT, asks_for: profile(v.url).asks, title: 'Fine payment' }
  }
  return { ...v }
}

// --- reports ----------------------------------------------------------------------------------------

const step = (id: string, done: boolean, when: string | null, en: string, ar: string): Step => ({ id, done, at: when, en, ar })

interface Fixture { id: string; url: string; age: number; status: string; verdict: string; brand: string | null; blocked: number }

/** One report in every status, newest first. */
const FIXTURES: Fixture[] = [
  { id: 'KP-7Q4M2D', url: 'https://tamm-fines-pay.top/ae/pay', age: 4 * MIN, status: 'sent', verdict: 'pending', brand: 'TAMM', blocked: 0 },
  { id: 'KP-3HX9RW', url: 'https://uaepass-verify.live/login', age: 38 * MIN, status: 'analysed', verdict: 'warn', brand: 'UAE PASS', blocked: 0 },
  { id: 'KP-8LC5TN', url: 'https://emirates-post-parcel.shop/track', age: 3 * HOUR, status: 'in_review', verdict: 'block', brand: 'Emirates Post', blocked: 6 },
  { id: 'KP-2VB7KJ', url: 'https://rta-fine-ae.xyz/payment', age: 26 * HOUR, status: 'confirmed', verdict: 'block', brand: 'RTA', blocked: 37 },
  { id: 'KP-5ZP1GE', url: 'https://salik-topup.click/renew', age: 4 * DAY, status: 'taken_down', verdict: 'block', brand: 'Salik', blocked: 214 },
  { id: 'KP-9NM3FA', url: 'https://myparcel-help.info/', age: 6 * DAY, status: 'rejected', verdict: 'warn', brand: null, blocked: 0 },
]

const ORDER = ['sent', 'analysed', 'in_review', 'confirmed', 'taken_down']

function timeline(f: Fixture, createdMs: number): ReportStatus {
  const reached = (s: string) => f.status === 'rejected' ? ['sent', 'analysed', 'in_review'].includes(s) : ORDER.indexOf(s) <= ORDER.indexOf(f.status)
  const span = Date.now() - createdMs
  const steps: Step[] = [step('sent', true, at(createdMs, 0), 'Report sent', 'تم إرسال البلاغ')]
  steps.push(step('analysed', reached('analysed'), reached('analysed') ? at(createdMs, Math.min(span, 2 * MIN) * 0.4) : null,
    f.verdict === 'block' ? 'Checked: high risk' : f.verdict === 'warn' ? 'Checked: suspicious' : 'Checking the link',
    f.verdict === 'block' ? 'تم الفحص: خطر مرتفع' : f.verdict === 'warn' ? 'تم الفحص: مشبوه' : 'جارٍ فحص الرابط'))
  steps.push(step('in_review', reached('in_review'), null, 'In police review', 'قيد مراجعة الشرطة'))
  if (f.status === 'rejected') {
    steps.push(step('rejected', true, at(createdMs, span * 0.5), 'Not enough evidence that this is a scam', 'لا توجد أدلة كافية على أنه احتيال'))
  } else if (reached('confirmed')) {
    steps.push(step('confirmed', true, at(createdMs, span * 0.35), 'Confirmed as a scam by police', 'أكدت الشرطة أنه احتيال'))
    steps.push(step('taken_down', reached('taken_down'), reached('taken_down') ? at(createdMs, span * 0.7) : null, 'Site taken down', 'تم إيقاف الموقع'))
  }
  const times = f.blocked === 1 ? 'time' : 'times'
  steps.push(step('impact', f.blocked > 0, null, `Blocked ${f.blocked} ${times} for other residents`, `تم حظره ${f.blocked} مرة لحماية سكان آخرين`))
  return { report_id: f.id, url: f.url, status: f.status, verdict: f.verdict, brand: f.brand, created_at: at(createdMs, 0), blocked_count: f.blocked, steps }
}

/** Reports sent in demo mode: their status follows the time since they were sent. */
const live = new Map<string, { url: string; created: number }>()
const LIVE_KEY = 'kp.demo.live'
try {
  for (const [id, v] of Object.entries(JSON.parse(localStorage.getItem(LIVE_KEY) ?? '{}') as Record<string, { url: string; created: number }>)) live.set(id, v)
} catch {
  /* ignore */
}

function liveStatus(id: string, url: string, created: number): ReportStatus {
  const p = profile(url)
  const age = Date.now() - created
  const risky = p.verdict !== 'allow'
  const status = age < 15_000 ? 'sent' : !risky ? 'analysed' : age < 40_000 ? 'analysed' : age < 90_000 ? 'in_review' : p.verdict === 'block' ? 'confirmed' : 'rejected'
  const blocked = status === 'confirmed' ? Math.floor((age - 90_000) / 20_000) + 1 : 0
  return timeline({ id, url, age, status, verdict: age < 15_000 ? 'pending' : p.verdict, brand: p.brand, blocked }, created)
}

export const DEMO_REPORTS_KEY = 'kp.demo.reports'

/** The fixtures go into the demo report list once, so "remove from this phone" sticks. */
export function seedReports(): void {
  try {
    if (localStorage.getItem(DEMO_REPORTS_KEY) !== null) return
    const list = FIXTURES.map((f) => ({ id: f.id, token: 'demo', url: f.url, at: ago(f.age) }))
    localStorage.setItem(DEMO_REPORTS_KEY, JSON.stringify(list))
  } catch {
    /* private mode: the demo list is empty */
  }
}

// --- radar ------------------------------------------------------------------------------------------

/** Radar numbers creep up while the page is open (one new RTA and parcel site every couple of minutes). */
const openedAt = Date.now()

function radarData(): Radar {
  const grow = Math.floor((Date.now() - openedAt) / 120_000)
  const brand = (brand_id: string, name: string, ar: string, category: string, confirmed: number, suspected: number, new_today: number,
    yesterday: number, examples: string[], tipEn: string, tipAr: string, safe: string) => ({
    brand_id, brand: name, brand_ar: ar, category, confirmed, suspected, active: confirmed + suspected, new_today, yesterday, examples,
    tip_en: tipEn, tip_ar: tipAr, safe_action: SAFE[safe] ?? null,
  })
  const brands = [
    brand('rta', 'RTA', 'هيئة الطرق والمواصلات', 'government', 48, 19 + grow, 14 + grow, 9, ['rta-fine-ae[.]xyz', 'rta-pay[.]top', 'rta-ae-fines[.]sbs'],
      'RTA never sends fine links by SMS. Check fines in the RTA app.', 'لا ترسل الهيئة روابط المخالفات عبر الرسائل. تحقّق من المخالفات في تطبيق الهيئة.', 'RTA'),
    brand('emiratespost', 'Emirates Post', 'بريد الإمارات', 'delivery', 36, 22 + Math.floor(grow / 2), 11 + Math.floor(grow / 2), 12, ['emirates-post-parcel[.]shop', 'epost-redeliver[.]icu'],
      'A parcel "held for a small fee" is the most common trick this week.', 'رسالة «شحنة محتجزة مقابل رسوم بسيطة» هي الخدعة الأكثر انتشارًا هذا الأسبوع.', 'Emirates Post'),
    brand('tamm', 'TAMM', 'تم', 'government', 27, 8, 6, 3, ['tamm-fines-pay[.]top'],
      'Pay government fees only inside the TAMM app or tamm.abudhabi.', 'ادفع الرسوم الحكومية فقط عبر تطبيق تم أو tamm.abudhabi.', 'TAMM'),
    brand('uaepass', 'UAE PASS', 'الهوية الرقمية', 'identity', 19, 13, 4, 5, ['uaepass-verify[.]live'],
      'UAE PASS never asks for your password on another website.', 'لا تطلب الهوية الرقمية كلمة مرورك على موقع آخر.', 'UAE PASS'),
    brand('dubaipolice', 'Dubai Police', 'شرطة دبي', 'police', 14, 5, 3, 3, ['dxb-police-fines[.]top'],
      'Dubai Police never asks you to pay fines through a link in an SMS.', 'لا تطلب شرطة دبي دفع المخالفات عبر رابط في رسالة نصية.', 'RTA'),
    brand('salik', 'Salik', 'سالك', 'government', 12, 4, 2, 1, ['salik-topup[.]click'],
      'Top up Salik only in the Salik app.', 'اشحن سالك فقط من تطبيق سالك.', 'Salik'),
    brand('emiratesnbd', 'Emirates NBD', 'بنك الإمارات دبي الوطني', 'bank', 8, 7, 0, 2, ['enbd-secure-login[.]online'],
      'Your bank never asks for your card PIN or OTP on a website.', 'لا يطلب بنكك رقمك السري أو رمز التحقق على أي موقع.', 'UAE PASS'),
    brand('etisalat', 'e& (Etisalat)', 'اتصالات', 'telecom', 9, 6, 1, 2, ['eand-rewards[.]online'],
      '"Points about to expire" messages lead to fake bill pages.', 'رسائل «نقاطك على وشك الانتهاء» تقود إلى صفحات فواتير مزيفة.', 'Etisalat'),
  ].sort((a, b) => b.active - a.active)
  const sum = (k: 'confirmed' | 'suspected' | 'active' | 'new_today' | 'yesterday') => brands.reduce((n, b) => n + b[k], 0)
  const TEXT: Record<string, [string, string]> = {
    government: ['fake government service sites', 'مواقع خدمات حكومية مزيفة'], delivery: ['fake parcel delivery sites', 'مواقع مزيفة لتوصيل الطرود'],
    identity: ['fake identity and login sites', 'مواقع مزيفة للهوية وتسجيل الدخول'], police: ['fake police and fine-payment sites', 'مواقع مزيفة للشرطة ودفع المخالفات'],
    bank: ['fake banking sites', 'مواقع بنكية مزيفة'], telecom: ['fake telecom sites', 'مواقع اتصالات مزيفة'],
  }
  const groups = new Map<string, { category: string; active: number; new_today: number; brands: string[] }>()
  for (const b of brands) {
    const g = groups.get(b.category) ?? { category: b.category, active: 0, new_today: 0, brands: [] }
    g.active += b.active
    g.new_today += b.new_today
    g.brands.push(b.brand)
    groups.set(b.category, g)
  }
  const headlines = [...groups.values()].sort((a, b) => b.active - a.active).map((g) => {
    const [en, ar] = TEXT[g.category] ?? ['scam sites', 'مواقع احتيال']
    const imitating = g.brands.slice(0, 3).join(', ')
    return { ...g, en: `${g.active} ${en} active, imitating ${imitating}`, ar: `${g.active} ${ar} نشطة، تقلّد ${imitating}` }
  })
  return {
    generated_at: new Date().toISOString(), window_days: 7,
    totals: { active: sum('active'), confirmed: sum('confirmed'), suspected: sum('suspected'), new_today: sum('new_today'), yesterday: sum('yesterday') },
    headlines, brands,
  }
}

// --- SMS paste --------------------------------------------------------------------------------------

function smsResult(text: string): SmsResult {
  const urls = (text.match(/https?:\/\/[^\s<>"']+|\b[a-z0-9-]+(\.[a-z0-9-]+)+\/[^\s]*/gi) ?? []).slice(0, 5)
  const links = urls.map((u) => verdictFor(/^https?:/i.test(u) ? u : `https://${u}`))
  const lower = text.toLowerCase()
  const kind: [RegExp, string, string, string][] = [
    [/fine|مخالف|violation/, 'fines', 'traffic fine', 'مخالفة مرورية'],
    [/parcel|deliver|شحن|طرد/, 'delivery', 'parcel delivery', 'توصيل طرود'],
    [/uae ?pass|password|account|حساب/, 'login', 'account sign-in', 'تسجيل دخول'],
    [/prize|won|reward|points|جائزة|نقاط/, 'prize', 'prize or reward', 'جائزة أو مكافأة'],
  ]
  const hit = kind.find(([re]) => re.test(lower))
  return {
    links, found_links: urls.length,
    text: { category: hit?.[1] ?? null, category_en: hit?.[2] ?? null, category_ar: hit?.[3] ?? null,
      urgent: /today|now|immediately|24 ?h|اليوم|فورا|فورًا/.test(lower), by: 'demo' },
  }
}

// --- router -----------------------------------------------------------------------------------------

const pause = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms))

/** Answers an /api path the way core would, after a short delay so loading states show; null is a 404. */
export async function handle(path: string, init: RequestInit): Promise<unknown> {
  await pause(250 + Math.random() * 350)
  const body = init.body ? JSON.parse(String(init.body)) as Record<string, string> : {}
  if (path === '/v1/check') return verdictFor(body.url)
  if (path.startsWith('/v1/check/')) return followCheck(decodeURIComponent(path.slice(10).split('?')[0]))
  if (path === '/v1/preview') return verdictFor(body.url, true)
  if (path === '/v1/radar') return radarData()
  if (path === '/v1/sms') return smsResult(body.text ?? '')
  if (path === '/v1/report') {
    const id = `KP-${Math.random().toString(36).slice(2, 8).toUpperCase()}`
    live.set(id, { url: body.url, created: Date.now() })
    try {
      localStorage.setItem(LIVE_KEY, JSON.stringify(Object.fromEntries(live)))
    } catch {
      /* ignore */
    }
    return { report_id: id, token: 'demo', check_id: verdictFor(body.url).check_id }
  }
  if (path.startsWith('/v1/reports/')) {
    const id = decodeURIComponent(path.slice(12))
    const fixture = FIXTURES.find((f) => f.id === id)
    if (fixture) return timeline(fixture, seededAt(id) ?? Date.now() - fixture.age)
    const sent = live.get(id)
    if (sent) return liveStatus(id, sent.url, sent.created)
  }
  return null
}

/** When a fixture was put into the demo list, so its dates stay put between refreshes. */
function seededAt(id: string): number | null {
  try {
    const list = JSON.parse(localStorage.getItem(DEMO_REPORTS_KEY) ?? '[]') as { id: string; at: string }[]
    const found = list.find((r) => r.id === id)
    return found ? Date.parse(found.at) : null
  } catch {
    return null
  }
}
