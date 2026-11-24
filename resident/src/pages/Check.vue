<script setup lang="ts">
// "Check a link": Link X-ray, the verdict card with the real-service button, the safe preview and Report.
// Also the target of the share sheet (/check?url= or ?text=) and of Gatekeeper's WebView (?source=gatekeeper).
import { computed, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { askPreview, checkLink, getCheck, previewSrc, sendReport, type Verdict } from '../api'
import XRay from '../components/XRay.vue'
import { ASKS, lang, tr } from '../i18n'
import { defang, hostOf, saveReport } from '../store'

const route = useRoute()
const router = useRouter()
const input = ref('')
const result = ref<Verdict | null>(null)
const checking = ref(false)
const error = ref('')
const note = ref('')
const reported = ref<string | null>(null)
const busy = ref(false)
let poll: number | undefined
let polls = 0

function firstUrl(text: string): string | null {
  const match = /https?:\/\/[^\s<>"']+/i.exec(text)
  return match ? match[0] : null
}

const target = computed(() => {
  const url = typeof route.query.url === 'string' ? route.query.url : ''
  const text = typeof route.query.text === 'string' ? route.query.text : ''
  return url || firstUrl(text) || ''
})
const source = computed(() => {
  const s = route.query.source
  return s === 'gatekeeper' || s === 'share' ? s : route.query.text || route.query.url ? 'share' : 'resident'
})

async function run(url: string) {
  window.clearTimeout(poll)
  result.value = null
  error.value = ''
  reported.value = null
  checking.value = true
  try {
    result.value = await checkLink(url, source.value)
    polls = 0
    follow()
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    checking.value = false
  }
}

function follow() {
  const current = result.value
  if (!current || !['queued', 'running'].includes(current.deep_status ?? '') || polls > 45) return
  poll = window.setTimeout(async () => {
    polls += 1
    try {
      result.value = await getCheck(current.check_id)
    } catch {
      /* keep the last answer */
    }
    follow()
  }, 2000)
}

watch(target, (url) => { if (url) run(url) }, { immediate: true })
onUnmounted(() => window.clearTimeout(poll))

function submit() {
  const url = input.value.trim()
  if (!url) return
  const full = /^https?:\/\//i.test(url) ? url : `https://${url}`
  router.push({ name: 'check', query: { url: full } })
}

async function preview() {
  if (!target.value) return
  busy.value = true
  try {
    result.value = await askPreview(target.value)
    polls = 0
    follow()
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = false
  }
}

async function report() {
  if (!target.value) return
  busy.value = true
  try {
    const sent = await sendReport(target.value, note.value)
    saveReport({ id: sent.report_id, token: sent.token, url: target.value, at: new Date().toISOString() })
    reported.value = sent.report_id
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = false
  }
}

const headline = computed(() => {
  switch (result.value?.verdict) {
    case 'block': return tr('⚠️ Suspected scam', '⚠️ احتيال مشتبه به')
    case 'warn': return tr('Be careful with this link', 'انتبه لهذا الرابط')
    case 'allow': return tr('No warning signs found', 'لم نجد علامات خطر')
    default: return tr('Checking link…', 'جارٍ فحص الرابط…')
  }
})
const deepRunning = computed(() => ['queued', 'running'].includes(result.value?.deep_status ?? ''))
const shot = computed(() => result.value?.preview?.screenshot ?? null)
const asks = computed(() => (result.value?.preview?.asks_for ?? []).map((a) => ASKS[a] ? tr(ASKS[a][0], ASKS[a][1]) : a))
</script>

<template>
  <main>
    <form class="card stack" @submit.prevent="submit">
      <label for="u"><strong>{{ tr('Check a link before you open it', 'افحص الرابط قبل فتحه') }}</strong></label>
      <input id="u" v-model="input" dir="ltr" inputmode="url" autocomplete="off" placeholder="https://…" />
      <button class="primary" :disabled="checking">{{ tr('Check', 'افحص') }}</button>
    </form>

    <template v-if="target">
      <p class="small muted">{{ tr('Link', 'الرابط') }}: <span class="domain">{{ defang(hostOf(target)) }}</span></p>
      <XRay :sources="result?.sources ?? null" />
      <p v-if="error" class="error">{{ error }}</p>

      <section v-if="result" class="card verdict" :class="result.verdict">
        <h1>{{ headline }}</h1>
        <p v-if="result.brand && result.verdict !== 'allow'">{{ tr(`This page pretends to be ${result.brand}.`, `هذه الصفحة تنتحل صفة ${result.brand}.`) }}</p>
        <ul class="reasons">
          <li v-for="r in result.reasons" :key="r.code">{{ lang === 'ar' ? r.ar : r.en }}</li>
        </ul>
        <a v-if="result.safe_action" class="button safe" :href="result.safe_action.url" rel="noopener">
          {{ lang === 'ar' ? result.safe_action.label_ar : result.safe_action.label_en }}
        </a>
        <p v-if="result.verdict === 'allow'" class="small muted">{{ tr('Still be careful: never share a one-time code with anyone.', 'كن حذرًا دائمًا: لا تشارك رمز التحقق مع أي أحد.') }}</p>
      </section>

      <section v-if="result" class="card">
        <h2>{{ tr('Safe preview', 'معاينة آمنة') }}</h2>
        <template v-if="shot">
          <p v-if="asks.length" class="asks">{{ tr('This page asks for', 'هذه الصفحة تطلب') }}: {{ asks.join(' · ') }}</p>
          <img class="shot" :src="previewSrc(shot)" :alt="tr('Picture of the page. Nothing on it can be tapped.', 'صورة للصفحة، لا يمكن الضغط على أي شيء فيها.')" />
          <p class="small muted">{{ tr('A picture taken in our sandbox. Nothing on it is a link.', 'صورة التُقطت في بيئة معزولة، ولا يحتوي أي جزء منها على رابط.') }}</p>
        </template>
        <p v-else-if="deepRunning" class="muted">{{ tr('Opening the page safely in our sandbox…', 'نفتح الصفحة بأمان في بيئة معزولة…') }}</p>
        <button v-else-if="result.score < 30" :disabled="busy" @click="preview">{{ tr('Show safe preview', 'اعرض معاينة آمنة') }}</button>
        <p v-else-if="result.reasons.some((r) => r.code === 'BLOCKLISTED')" class="muted small">{{ tr('Police have already confirmed this site as a scam.', 'أكدت الشرطة مسبقًا أن هذا الموقع احتيالي.') }}</p>
        <p v-else class="muted small">{{ tr('No preview: the page could not be opened.', 'لا توجد معاينة: تعذّر فتح الصفحة.') }}</p>
      </section>

      <section v-if="result" class="card stack">
        <h2>{{ tr('Report to police', 'أبلغ الشرطة') }}</h2>
        <template v-if="!reported">
          <textarea v-model="note" maxlength="2000" :placeholder="tr('Optional: where did you get this link? Do not write card numbers or codes.', 'اختياري: من أين وصلك هذا الرابط؟ لا تكتب أرقام بطاقات أو رموز.')" />
          <button :disabled="busy" @click="report">{{ tr('Report', 'إبلاغ') }}</button>
        </template>
        <p v-else>{{ tr('Thank you. Follow it in My reports.', 'شكرًا لك. تابع البلاغ في بلاغاتي.') }} <RouterLink to="/reports">{{ tr('My reports', 'بلاغاتي') }}</RouterLink></p>
      </section>
    </template>
  </main>
</template>

<style scoped>
.verdict.block { border-color: var(--block); background: var(--block-soft); }
.verdict.warn { border-color: var(--warn); background: var(--warn-soft); }
.verdict.allow { border-color: var(--allow); background: var(--allow-soft); }
.verdict.block h1 { color: var(--block); }
.reasons { padding-inline-start: 1.2rem; margin: 0.5rem 0 0.9rem; }
.shot { width: 100%; border: 1px solid var(--line); border-radius: 10px; pointer-events: none; user-select: none; }
.asks { background: var(--block-soft); color: var(--block); font-weight: 600; padding: 0.5rem 0.75rem; border-radius: 10px; }
</style>
