<script setup lang="ts">
// One campaign (D3): graph, site table with ticks, "Confirm ticked", exclude, merge, and leads from a pivot.
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { get, onEvent, post } from '../api'
import CampaignGraphView from '../components/CampaignGraph.vue'
import DefangedDomain from '../components/DefangedDomain.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { t } from '../i18n'
import { reviewer } from '../session'
import type { CampaignDetail, CampaignGraph, Lead } from '../types'

const props = defineProps<{ id: string }>()
const router = useRouter()
const detail = ref<CampaignDetail | null>(null)
const graph = ref<CampaignGraph | null>(null)
const ticked = ref<Set<string>>(new Set())
const leads = ref<Lead[] | null>(null)
const pivotOn = ref('')
const mergeWith = ref('')
const note = ref('')
const error = ref('')
const notice = ref('')
const busy = ref(false)

async function load() {
  error.value = ''
  try {
    detail.value = await get<CampaignDetail>(`/v1/admin/campaigns/${encodeURIComponent(props.id)}`)
    graph.value = await get<CampaignGraph>(`/v1/admin/campaigns/${encodeURIComponent(props.id)}/graph`)
    ticked.value = new Set(detail.value.domains.filter((d) => d.tick).map((d) => d.domain))
  } catch (e) {
    error.value = (e as Error).message
  }
}

const graphView = ref<InstanceType<typeof CampaignGraphView> | null>(null)

// A site that joins this campaign while the page is open: reload, then point at it in the graph.
let stop: (() => void) | undefined
onMounted(() => {
  load()
  stop = onEvent(async (event) => {
    if (event.type !== 'campaign.new_domain' || event.campaign_id !== props.id) return
    await load()
    await nextTick()
    window.setTimeout(() => graphView.value?.pulse(`d:${String(event.domain)}`), 950)
  })
})
onUnmounted(() => stop?.())
watch(() => props.id, load)

const tickable = computed(() => detail.value?.domains.filter((d) => d.status !== 'confirmed') ?? [])

function toggle(domain: string) {
  const next = new Set(ticked.value)
  if (next.has(domain)) next.delete(domain)
  else next.add(domain)
  ticked.value = next
}

async function run(fn: () => Promise<string>) {
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    notice.value = await fn()
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = false
  }
}

function confirmAll() {
  const domains = [...ticked.value]
  if (!domains.length) return
  if (!window.confirm(`Confirm ${domains.length} site(s) as scams? Each gets its own review and goes on the blocklist.`)) return
  run(async () => {
    const result = await post<{ confirmed: { display: string }[]; refused: { display: string; why: string }[] }>(
      `/v1/admin/campaigns/${encodeURIComponent(props.id)}/confirm`, { domains, reviewer: reviewer(), note: note.value })
    await load()
    const refused = result.refused.map((r) => `${r.display} (${r.why})`).join(', ')
    return `Confirmed ${result.confirmed.length}.${refused ? ` Refused: ${refused}.` : ''}`
  })
}

function exclude(domain: string) {
  const reason = window.prompt('Why does this site not belong to the campaign?')
  if (!reason) return
  run(async () => {
    await post(`/v1/admin/campaigns/${encodeURIComponent(props.id)}/exclude`, { domain, reviewer: reviewer(), reason })
    await load()
    return 'Excluded.'
  })
}

function merge() {
  const other = mergeWith.value.trim()
  if (!other) return
  const reason = window.prompt('Why are these the same campaign?')
  if (!reason) return
  run(async () => {
    const result = await post<{ id: string; merged: string[] }>('/v1/admin/campaigns/merge',
      { ids: [props.id, other], reviewer: reviewer(), reason })
    mergeWith.value = ''
    if (result.id !== props.id) {
      await router.push({ name: 'campaign', params: { id: result.id } })
    } else {
      await load()
    }
    return `Merged ${result.merged.join(', ')} into ${result.id}.`
  })
}

function pivot(nodeId?: string) {
  let body: { kind?: string; value?: string } = {}
  if (nodeId && !nodeId.startsWith('d:')) {
    const at = nodeId.indexOf(':')
    const kind = nodeId.slice(0, at)
    const entity = detail.value?.entities.find((e) => e.kind === kind && nodeId === `${kind}:${e.value}`)
    body = { kind, value: entity?.value ?? nodeId.slice(at + 1) }
    pivotOn.value = entity?.label ?? nodeId
  } else {
    pivotOn.value = 'all entities'
  }
  run(async () => {
    const result = await post<{ leads: Lead[]; total: number }>(`/v1/admin/campaigns/${encodeURIComponent(props.id)}/pivot`, body)
    leads.value = result.leads
    return ''
  })
}

function select(nodeId: string) {
  if (nodeId.startsWith('d:')) return
  pivot(nodeId)
}
</script>

<template>
  <main class="page">
    <RouterLink :to="{ name: 'campaigns' }" class="small">← {{ t('campaigns.title') }}</RouterLink>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="notice" class="notice">{{ notice }}</p>
    <template v-if="detail">
      <div class="row">
        <h1>{{ detail.name ?? detail.id }}</h1>
        <StatusBadge :value="detail.status" />
        <span class="muted small mono">{{ detail.id }}</span>
        <span class="spacer" />
        <input v-model="mergeWith" size="14" placeholder="cmp_…" />
        <button :disabled="busy || !mergeWith" @click="merge">{{ t('campaign.merge') }}</button>
      </div>
      <p class="muted small">{{ detail.domain_count }} sites · {{ detail.confirmed_count }} confirmed · since {{ new Date(detail.first_seen).toLocaleDateString() }}</p>
      <div class="grid cols-2">
        <div class="card">
          <CampaignGraphView v-if="graph" ref="graphView" :graph="graph" @select="select" />
          <p class="muted small">Click an entity to list other sites that use it.</p>
          <h3>Linking entities</h3>
          <table class="small">
            <tr v-for="e in detail.entities" :key="e.kind + e.value" class="clickable" @click="pivot(`${e.kind}:${e.value}`)">
              <td>{{ e.kind }}</td><td class="mono">{{ e.label }}</td>
              <td><span class="badge" :class="e.strength === 'strong' ? 'block' : ''">{{ e.strength }}</span></td>
              <td>{{ e.in_campaign }} here · {{ e.domain_count }} total</td>
            </tr>
          </table>
        </div>
        <div>
          <div class="card">
            <div class="row">
              <h2>Sites</h2><span class="spacer" />
              <button class="primary" :disabled="busy || !ticked.size" @click="confirmAll">{{ t('campaign.confirmAll') }} ({{ ticked.size }})</button>
            </div>
            <input v-model="note" class="full" :placeholder="t('case.note')" />
            <table>
              <tr><th></th><th>site</th><th>score</th><th>links</th><th></th></tr>
              <tr v-for="d in detail.domains" :key="d.domain">
                <td><input type="checkbox" :disabled="!tickable.includes(d)" :checked="ticked.has(d.domain)" @change="toggle(d.domain)" /></td>
                <td><RouterLink :to="{ name: 'case', params: { domain: d.domain } }"><DefangedDomain :display="d.display" /></RouterLink>
                  <div><StatusBadge v-if="d.status" :value="d.status" /></div></td>
                <td><StatusBadge :value="d.verdict" :score="d.score" /></td>
                <td class="small">{{ d.links.join(', ') }}</td>
                <td><button class="ghost small" :disabled="busy" @click="exclude(d.domain)">{{ t('campaign.exclude') }}</button></td>
              </tr>
            </table>
            <p class="muted small">Sites scoring below 70 start unticked. Official and allowlisted sites are always refused.</p>
          </div>
          <div class="card">
            <div class="row"><h2>{{ t('campaign.pivot') }}</h2><span class="muted small">{{ pivotOn }}</span><span class="spacer" />
              <button :disabled="busy" @click="pivot()">All entities</button></div>
            <p v-if="leads && !leads.length" class="muted">No other sites use these entities.</p>
            <table v-if="leads?.length" class="small">
              <tr v-for="lead in leads" :key="lead.domain">
                <td><RouterLink :to="{ name: 'case', params: { domain: lead.domain } }"><DefangedDomain :display="lead.display" /></RouterLink></td>
                <td><StatusBadge v-if="lead.score !== null" :value="lead.status ?? 'score'" :score="lead.score" /></td>
                <td>{{ lead.via.map((v) => `${v.kind}${v.strong ? '' : ' (weak)'}`).join(', ') }}</td>
                <td class="mono">{{ lead.campaign ?? '' }}</td>
              </tr>
            </table>
          </div>
        </div>
      </div>
    </template>
  </main>
</template>

<style scoped>
.full { width: 100%; margin: 0.5rem 0; }
</style>
