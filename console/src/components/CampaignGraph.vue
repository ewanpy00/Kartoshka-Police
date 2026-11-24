<script setup lang="ts">
// Campaign graph (D3): sites and the entities they use. Weak links are present but hidden by default.
import cytoscape, { type Core, type ElementDefinition } from 'cytoscape'
import fcose from 'cytoscape-fcose'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { t } from '../i18n'
import type { CampaignGraph } from '../types'

cytoscape.use(fcose)

const props = defineProps<{ graph: CampaignGraph }>()
const emit = defineEmits<{ select: [id: string] }>()
const box = ref<HTMLDivElement | null>(null)
const showWeak = ref(false)
let cy: Core | null = null

const COLORS: Record<string, string> = {
  phone: '#b42318', whatsapp: '#1b7f4b', payment: '#a35f00', kit_hash: '#5b3aa6', favicon_hash: '#7a4fd1',
  cert: '#1f4e8c', ip: '#2f6f9f', officer_link: '#111827', asn: '#9aa3ae', registrar: '#9aa3ae', ns: '#9aa3ae', kit_sim: '#b8a6e0',
}

function elements(): ElementDefinition[] {
  const nodes: ElementDefinition[] = props.graph.nodes.map((n) => ({
    data: { id: n.id, label: n.label, kind: n.kind, status: n.status ?? '', hub: n.hub ? 1 : 0,
            color: n.kind === 'domain' ? (n.status === 'confirmed' ? '#b42318' : '#a35f00') : (COLORS[n.kind] ?? '#9aa3ae') },
  }))
  const edges: ElementDefinition[] = props.graph.edges.map((e, i) => ({
    data: { id: `e${i}`, source: e.source, target: e.target, strength: e.strength, excluded: e.excluded ? 1 : 0 },
  }))
  return [...nodes, ...edges]
}

function applyWeak() {
  if (!cy) return
  cy.edges('[strength = "weak"]').style('display', showWeak.value ? 'element' : 'none')
  cy.nodes().forEach((node) => {
    if (node.data('kind') === 'domain') return
    const visible = node.connectedEdges().some((edge) => edge.style('display') !== 'none')
    node.style('display', visible ? 'element' : 'none')
  })
}

function render() {
  if (!box.value) return
  cy?.destroy()
  cy = cytoscape({
    container: box.value,
    elements: elements(),
    wheelSensitivity: 0.3,
    style: [
      { selector: 'node', style: { 'background-color': 'data(color)', label: 'data(label)', 'font-size': 9, color: '#1c2430',
        'text-valign': 'bottom', 'text-margin-y': 3, width: 14, height: 14 } },
      { selector: 'node[kind = "domain"]', style: { shape: 'round-rectangle', width: 22, height: 22, 'font-size': 10, 'font-weight': 'bold' } },
      { selector: 'node[hub = 1]', style: { 'border-width': 2, 'border-color': '#9aa3ae', 'border-style': 'dashed' } },
      { selector: 'edge', style: { width: 2, 'line-color': '#5f6b7a', 'curve-style': 'bezier' } },
      { selector: 'edge[strength = "weak"]', style: { width: 1, 'line-style': 'dashed', 'line-color': '#c2c8d0' } },
      { selector: 'edge[excluded = 1]', style: { 'line-color': '#e2a59f', 'line-style': 'dotted' } },
      { selector: ':selected', style: { 'border-width': 3, 'border-color': '#1f4e8c' } },
    ],
    layout: { name: 'fcose', animate: false, randomize: true, nodeRepulsion: () => 6000, idealEdgeLength: () => 70 } as cytoscape.LayoutOptions,
  })
  cy.on('tap', 'node', (event) => emit('select', event.target.id()))
  applyWeak()
}

onMounted(render)
watch(() => props.graph, render)
watch(showWeak, applyWeak)
onBeforeUnmount(() => cy?.destroy())
</script>

<template>
  <div>
    <div class="row small">
      <label><input v-model="showWeak" type="checkbox" /> {{ t('campaign.weak') }}</label>
      <span v-for="c in graph.collapsed" :key="c.kind" class="badge">+{{ c.count }} {{ c.kind }}</span>
      <span class="spacer" />
      <span class="muted">— strong · - - weak · ▢ site</span>
    </div>
    <div ref="box" class="graph" />
  </div>
</template>

<style scoped>
.graph { height: 460px; border: 1px solid var(--line); border-radius: 6px; background: var(--surface-2); margin-top: 0.5rem; direction: ltr; }
</style>
