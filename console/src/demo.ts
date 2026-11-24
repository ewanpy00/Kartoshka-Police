// Demo mode: a guided tour of the console with a visible cursor, for presentations and screen recordings.
//
// The tour only clicks controls that read data (navigation, filters, opening a case, the chain check).
// Controls that write (Confirm, Reject, Build packs) get `point`: the cursor rests on them and the caption
// explains them, but nothing is sent. A step whose element is not on the page is skipped.
import { ref } from 'vue'
import type { Router } from 'vue-router'
import type { Key } from './i18n'
import { officer, signIn } from './session'
import type { FeedRow } from './types'

export type DemoAction = 'click' | 'point'

export interface DemoStep {
  /** CSS selector of the element the cursor goes to. */
  target: string
  action: DemoAction
  caption: Key
  /** How long the caption stays after the cursor arrives, in ms. */
  hold?: number
  /** Something to start when the cursor arrives: `feed` streams sample rows into the Hunter feed. */
  effect?: 'feed'
}

// The main story only, in about 35 seconds: a case, its campaign, the takedown, the live Hunter, the impact and
// the evidence chain. Controls that write are only pointed at.
export const DEMO_STEPS: readonly DemoStep[] = [
  { target: '.sidenav a[href="/queue"]', action: 'click', caption: 'demoQueue', hold: 900 },
  { target: '.chips .chip:nth-child(2)', action: 'click', caption: 'demoHighRisk', hold: 700 },
  { target: '.q-row', action: 'click', caption: 'demoOpenCase', hold: 700 },
  { target: '.case-card .case-head-score', action: 'point', caption: 'demoScore' },
  { target: '.case-card .reason-list', action: 'point', caption: 'demoReasons', hold: 1600 },
  { target: '.case-card .shot', action: 'point', caption: 'demoShot' },
  { target: '.case-card .action-row .btn.primary', action: 'point', caption: 'demoConfirm', hold: 1500 },
  { target: '.sidenav a[href="/campaigns"]', action: 'click', caption: 'demoCampaigns', hold: 700 },
  { target: '.content table a.link', action: 'click', caption: 'demoCampaign', hold: 600 },
  { target: '.content .graph', action: 'point', caption: 'demoGraph', hold: 1500 },
  { target: '.sidenav a[href="/takedowns"]', action: 'click', caption: 'demoTakedowns', hold: 700 },
  { target: '.content .table:has(.status-chip)', action: 'point', caption: 'demoTdRequests', hold: 1400 },
  { target: '.sidenav a[href="/feed"]', action: 'click', caption: 'demoFeed', hold: 600 },
  // The feed card is there even before the real feed answers, so the sample rows can stream in at once.
  { target: '.content .queue-layout > .card', action: 'point', caption: 'demoFeedLive', hold: 2600, effect: 'feed' },
  { target: '.sidenav a[href="/impact"]', action: 'click', caption: 'demoImpact', hold: 700 },
  { target: '.content .stat-strip', action: 'point', caption: 'demoImpactTotals', hold: 1500 },
  { target: '.sidenav a[href="/chain"]', action: 'click', caption: 'demoChain', hold: 600 },
  { target: '.content .page-head .btn.primary', action: 'click', caption: 'demoChainCheck', hold: 600 },
  { target: '.content .status-chip', action: 'point', caption: 'demoChainResult', hold: 1200 },
  { target: '.sidenav a[href="/queue"]', action: 'click', caption: 'demoDone', hold: 1200 },
]

const MOVE_MS = 320
const CLICK_MS = 160
const HOLD_MS = 1000
// Long enough for a page to load its data on a busy backend; a step only waits this long when its element is missing.
const FIND_MS = 4000

export const demoRunning = ref(false)
export const demoCaption = ref<Key | null>(null)
export const demoStepIndex = ref(0)
export const demoCursor = ref({ x: 0, y: 0, visible: false, clicking: false })
export const demoRing = ref<{ x: number; y: number; w: number; h: number } | null>(null)
/** Sample Hunter rows that appear live during the demo. They live only in memory and are cleared on stop. */
export const demoFeedRows = ref<FeedRow[]>([])

const FEED_SAMPLES: readonly Omit<FeedRow, 'key' | 'at'>[] = [
  { type: 'hunter.candidate', domain: 'tamm-payment-portal.xyz', brand: 'TAMM', verdict: 'block', score: 94 },
  { type: 'hunter.candidate', domain: 'dewa-refund-now.online', brand: 'DEWA', verdict: 'block', score: 88 },
  { type: 'campaign.new_domain', domain: 'uaepass-login-verify.top', brand: 'UAE PASS', verdict: 'block', score: 91 },
  { type: 'hunter.candidate', domain: 'adpolice-fine-pay.shop', brand: 'Abu Dhabi Police', verdict: 'warn', score: 64 },
  { type: 'check.verdict', domain: 'emirates-post-parcel.info', brand: 'Emirates Post', verdict: 'warn', score: 58 },
]

let runId = 0
let feedTimer: ReturnType<typeof setInterval> | undefined

function streamFeed(): void {
  clearInterval(feedTimer)
  let i = 0
  const add = () => {
    const sample = FEED_SAMPLES[i % FEED_SAMPLES.length]
    demoFeedRows.value = [{ ...sample, key: `demo-${Date.now()}-${i}`, at: new Date().toISOString() }, ...demoFeedRows.value]
    i++
    if (i >= FEED_SAMPLES.length) clearInterval(feedTimer)
  }
  add()
  feedTimer = setInterval(add, 550)
}
let current: HTMLElement | null = null
let placedAt = ''
let follow: ReturnType<typeof setInterval> | undefined

function reducedMotion(): boolean {
  return window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches ?? false
}

/** Waits `ms`, then reports whether this run is still the current one. */
function wait(ms: number, id: number): Promise<boolean> {
  return new Promise((resolve) => setTimeout(() => resolve(id === runId), ms))
}

function visible(el: Element): boolean {
  const rect = el.getBoundingClientRect()
  return rect.width > 0 && rect.height > 0
}

/** The first visible match for `selector`, polling while the page loads its data. */
export async function findTarget(selector: string, timeout = FIND_MS): Promise<HTMLElement | null> {
  const end = Date.now() + timeout
  for (;;) {
    const match = [...document.querySelectorAll<HTMLElement>(selector)].find(visible)
    if (match) return match
    if (Date.now() >= end) return null
    await new Promise((resolve) => setTimeout(resolve, 100))
  }
}

function place(el: HTMLElement): void {
  const rect = el.getBoundingClientRect()
  placedAt = `${rect.left},${rect.top},${rect.width},${rect.height}`
  // Large targets (a list, a graph) get the cursor near their start, not lost in the middle.
  const big = rect.height > 160
  const rtl = document.documentElement.dir === 'rtl'
  const x = big ? (rtl ? rect.right - 48 : rect.left + 48) : rect.left + rect.width / 2
  const y = big ? rect.top + 48 : rect.top + rect.height / 2
  demoCursor.value = { ...demoCursor.value, x, y, visible: true }
  demoRing.value = { x: rect.left - 4, y: rect.top - 4, w: rect.width + 8, h: rect.height + 8 }
}

/** Waits until `el` stops moving (smooth scrolling has finished), up to `max` ms. */
async function settle(el: HTMLElement, id: number, max = 1500): Promise<boolean> {
  let last = el.getBoundingClientRect()
  for (let waited = 0; waited < max; waited += 60) {
    if (!(await wait(60, id))) return false
    const now = el.getBoundingClientRect()
    if (now.top === last.top && now.left === last.left) return true
    last = now
  }
  return id === runId
}

async function runStep(step: DemoStep, id: number): Promise<boolean> {
  const el = await findTarget(step.target)
  if (id !== runId) return false
  if (!el) return true // Nothing to show on this page (for example no campaigns yet): skip the step.
  const fast = reducedMotion()
  el.scrollIntoView?.({ block: 'center', inline: 'nearest', behavior: fast ? 'auto' : 'smooth' })
  if (!(await settle(el, id))) return false
  demoCaption.value = step.caption
  current = el
  place(el)
  if (step.effect === 'feed') streamFeed()
  if (!(await wait(fast ? 50 : MOVE_MS, id))) return false
  if (step.action === 'click') {
    demoCursor.value = { ...demoCursor.value, clicking: true }
    if (!(await wait(CLICK_MS, id))) return false
    demoCursor.value = { ...demoCursor.value, clicking: false }
    el.click()
  }
  return wait(step.hold ?? HOLD_MS, id)
}

function onKey(event: KeyboardEvent): void {
  if (event.key === 'Escape') stopDemo()
}

// Keep the cursor and ring on the current element when the page scrolls or resizes under them.
function onMove(): void {
  if (current?.isConnected) place(current)
  else demoRing.value = null
}

// Layout can also shift without a scroll event (data arriving, a scrollbar appearing), so check a few times a second.
function track(): void {
  if (!current?.isConnected) return
  const rect = current.getBoundingClientRect()
  if (`${rect.left},${rect.top},${rect.width},${rect.height}` !== placedAt) place(current)
}

export async function startDemo(router: Router, steps: readonly DemoStep[] = DEMO_STEPS): Promise<void> {
  const id = ++runId
  demoRunning.value = true
  demoStepIndex.value = 0
  demoCursor.value = { x: window.innerWidth / 2, y: window.innerHeight / 2, visible: true, clicking: false }
  window.addEventListener('keydown', onKey)
  window.addEventListener('resize', onMove)
  window.addEventListener('scroll', onMove, { capture: true, passive: true })
  clearInterval(follow)
  follow = setInterval(track, 200)
  if (!officer.value) signIn()
  await router.push('/queue')
  for (let i = 0; i < steps.length; i++) {
    demoStepIndex.value = i
    if (!(await runStep(steps[i], id))) return
  }
  if (id === runId) stopDemo()
}

export function stopDemo(): void {
  runId++
  demoRunning.value = false
  demoCaption.value = null
  demoRing.value = null
  demoCursor.value = { ...demoCursor.value, visible: false, clicking: false }
  window.removeEventListener('keydown', onKey)
  window.removeEventListener('resize', onMove)
  window.removeEventListener('scroll', onMove, { capture: true })
  current = null
  clearInterval(follow)
  clearInterval(feedTimer)
  demoFeedRows.value = []
}
