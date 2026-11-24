<script setup lang="ts">
// Impact (D6): volumes, a series chart, and lead time per confirmed domain that Hunter saw in CT.
import { BarController, BarElement, CategoryScale, Chart, Legend, LinearScale, LineController, LineElement, PointElement, Tooltip } from 'chart.js'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { get } from '../api'
import DefangedDomain from '../components/DefangedDomain.vue'
import { t } from '../i18n'
import { useCountUp } from '../motion'
import { cssVar, dark } from '../theme'
import type { Stats } from '../types'

Chart.register(BarController, BarElement, LineController, LineElement, PointElement, CategoryScale, LinearScale, Legend, Tooltip)

const range = ref<'24h' | '7d'>('24h')
const stats = ref<Stats | null>(null)
const error = ref('')
const canvas = ref<HTMLCanvasElement | null>(null)
let chart: Chart | null = null

const totals = computed(() => stats.value?.totals)
const threats = useCountUp(() => (totals.value ? totals.value.warn + totals.value.block : 0))
const candidates = useCountUp(() => totals.value?.candidates ?? 0)
const confirmed = useCountUp(() => totals.value?.confirmed ?? 0)
const rejected = useCountUp(() => totals.value?.rejected ?? 0)
const blockedVisits = useCountUp(() => Object.values(totals.value?.blocked_hits ?? {}).reduce((a, b) => a + b, 0))

async function load() {
  error.value = ''
  try {
    stats.value = await get<Stats>('/v1/admin/stats', { range: range.value })
    await nextTick()
    draw()
  } catch (e) {
    error.value = (e as Error).message
  }
}

function draw() {
  const s = stats.value
  if (!s || !canvas.value) return
  chart?.destroy()
  const [warn, accent, block, muted, line] = ['--warn', '--accent', '--block', '--muted', '--line'].map((name) => cssVar(name))
  Chart.defaults.color = muted
  Chart.defaults.borderColor = line
  const labels = s.series.buckets.map((b) => {
    const d = new Date(b)
    return range.value === '24h' ? `${d.getHours()}:00` : d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  })
  chart = new Chart(canvas.value, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        { label: 'warn / block checks', data: s.series.checks, backgroundColor: warn, borderRadius: 3 },
        { label: 'Hunter candidates', data: s.series.candidates, backgroundColor: accent, borderRadius: 3 },
        { type: 'line', label: 'confirmed', data: s.series.confirmed, borderColor: block, backgroundColor: block, tension: 0.35 },
      ],
    },
    options: { responsive: true, animation: { duration: 700, easing: 'easeOutCubic' }, maintainAspectRatio: false, scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } },
  })
}

function hrs(value: number | null, open = false): string {
  if (value === null) return '—'
  return `${open ? '≥ ' : ''}${value} h`
}

onMounted(load)
watch(range, load)
watch(dark, () => nextTick(draw))
onBeforeUnmount(() => chart?.destroy())
</script>

<template>
  <main class="page">
    <div class="row">
      <h1>{{ t('impact.title') }}</h1>
      <span class="spacer" />
      <button :class="{ primary: range === '24h' }" @click="range = '24h'">24 h</button>
      <button :class="{ primary: range === '7d' }" @click="range = '7d'">7 days</button>
    </div>
    <p v-if="error" class="error">{{ error }}</p>
    <template v-if="stats">
      <div class="grid cols-4">
        <div class="card"><div class="muted small">warn / block checks</div><div class="stat">{{ threats }}</div>
          <div class="small muted">{{ stats.totals.checks }} checks</div></div>
        <div class="card"><div class="muted small">Hunter candidates</div><div class="stat">{{ candidates }}</div>
          <div class="small muted">{{ Object.entries(stats.totals.candidates_by_source).map(([k, v]) => `${k} ${v}`).join(' · ') || '—' }}</div></div>
        <div class="card"><div class="muted small">confirmed / rejected</div><div class="stat">{{ confirmed }} / {{ rejected }}</div>
          <div class="small muted">blocklist {{ stats.totals.blocklist_size }} · taken down {{ stats.totals.taken_down }}</div></div>
        <div class="card"><div class="muted small">blocked visits</div><div class="stat">{{ blockedVisits }}</div>
          <div class="small muted">{{ Object.entries(stats.totals.blocked_hits).map(([k, v]) => `${k} ${v}`).join(' · ') || '—' }} · {{ stats.totals.reports }} reports</div></div>
      </div>
      <div class="card chart"><canvas ref="canvas" /></div>
      <div class="card">
        <h2>Lead time</h2>
        <p class="small muted">Officer-confirmed domains first seen in Certificate Transparency. Lead = when Google Safe Browsing or VirusTotal first flagged the domain, minus our first sighting; “≥” means they have not flagged it yet.</p>
        <div class="row small">
          <span>median time to confirm: <strong>{{ hrs(stats.lead_time.median_hours_to_confirm) }}</strong></span>
          <span>median lead vs GSB: <strong>{{ hrs(stats.lead_time.median_lead_vs_gsb_h) }}</strong></span>
          <span>median lead vs VirusTotal: <strong>{{ hrs(stats.lead_time.median_lead_vs_vt_h) }}</strong></span>
          <span>not yet in GSB: <strong>{{ stats.lead_time.not_flagged_by_gsb_yet }}</strong></span>
        </div>
        <p v-if="!stats.lead_time.domains.length" class="muted">No confirmed domain with a CT sighting yet.</p>
        <table v-else>
          <tr><th>domain</th><th>first seen (CT)</th><th>to confirm</th><th>lead vs GSB</th><th>lead vs VirusTotal</th></tr>
          <tr v-for="r in stats.lead_time.domains" :key="r.domain">
            <td><DefangedDomain :display="r.display" /></td>
            <td class="small">{{ new Date(r.seen).toLocaleString() }}</td>
            <td>{{ hrs(r.hours_to_confirm) }}</td>
            <td>{{ hrs(r.lead_vs_gsb_h, r.lead_vs_gsb_open) }}</td>
            <td>{{ hrs(r.lead_vs_vt_h, r.lead_vs_vt_open) }}</td>
          </tr>
        </table>
      </div>
    </template>
  </main>
</template>

<style scoped>
.chart { height: 300px; margin-top: 1rem; }
.stat { font-variant-numeric: tabular-nums; }
</style>
