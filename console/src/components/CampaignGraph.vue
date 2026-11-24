<script setup lang="ts">
// Campaign graph (D3): sites and the entities they use. Weak links are present but hidden by default.
import cytoscape, { type Core, type ElementDefinition } from 'cytoscape'
import fcose from 'cytoscape-fcose'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { t } from '../i18n'
import { reducedMotion } from '../motion'
import { cssVar, dark } from '../theme'
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
            color: n.kind === 'domain' ? (n.status === 'confirmed' ? cssVar('--block') : cssVar('--warn')) : (COLORS[n.kind] ?? '#9aa3ae') },
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
  const text = cssVar('--text')
  const edge = cssVar('--muted')
  const weak = cssVar('--line')
  const accent = cssVar('--accent')
  const block = cssVar('--block')
  cy = cytoscape({
    container: box.value,
    elements: elements(),
    wheelSensitivity: 0.3,
    style: [
      { selector: 'node', style: { 'background-color': 'data(color)', label: 'data(label)', 'font-size': 9, color: text, 'text-outline-color': cssVar('--surface-2'), 'text-outline-width': 2,
        'transition-property': 'width, height, underlay-opacity, underlay-padding', 'transition-duration': 300,
        'text-valign': 'bottom', 'text-margin-y': 3, width: 14, height: 14 } },
      { selector: 'node[kind = "domain"]', style: { shape: 'round-rectangle', width: 22, height: 22, 'font-size': 10, 'font-weight': 'bold' } },
      { selector: 'node[status = "confirmed"]', style: { 'underlay-color': block, 'underlay-padding': 7, 'underlay-opacity': dark.value ? 0.35 : 0.18,
        'underlay-shape': 'round-rectangle' } },
      { selector: 'node.pulse', style: { width: 34, height: 34, 'underlay-color': block, 'underlay-padding': 16, 'underlay-opacity': 0.45,
        'underlay-shape': 'ellipse' } },
      { selector: 'node.faded', style: { opacity: 0.25 } },
      { selector: 'edge.faded', style: { opacity: 0.12 } },
      { selector: 'node[hub = 1]', style: { 'border-width': 2, 'border-color': '#9aa3ae', 'border-style': 'dashed' } },
      { selector: 'edge', style: { width: 2, 'line-color': edge, opacity: 0.8, 'curve-style': 'bezier' } },
      { selector: 'edge[strength = "weak"]', style: { width: 1, 'line-style': 'dashed', 'line-color': weak } },
      { selector: 'edge[excluded = 1]', style: { 'line-color': '#e2a59f', 'line-style': 'dotted' } },
      { selector: 'edge.lit', style: { 'line-color': accent, width: 3, opacity: 1 } },
      { selector: ':selected', style: { 'border-width': 3, 'border-color': accent } },
    ],
    layout: { name: 'fcose', animate: !reducedMotion.value, animationDuration: 900, animationEasing: 'ease-out-cubic', randomize: true, nodeRepulsion: () => 6000, idealEdgeLength: () => 70 } as cytoscape.LayoutOptions,
  })
  cy.on('tap', 'node', (event) => emit('select', event.target.id()))
  // Hovering a node lights its neighbourhood and fades the rest, so a shared phone or kit reads at a glance.
  cy.on('mouseover', 'node', (event) => {
    const near = event.target.closedNeighborhood()
    cy?.elements().not(near).addClass('faded')
    near.edges().addClass('lit')
  })
  cy.on('mouseout', 'node', () => cy?.elements().removeClass('faded lit'))
  applyWeak()
}

/** Draws the eye to one node (a site that just joined the campaign). */
function pulse(id: string) {
  const node = cy?.getElementById(id)
  if (!node || node.empty()) return
  let left = 3
  const beat = () => {
    node.addClass('pulse')
    window.setTimeout(() => {
      node.removeClass('pulse')
      if (--left > 0) window.setTimeout(beat, 300)
    }, 450)
  }
  beat()
  if (!reducedMotion.value) cy?.animate({ center: { eles: node }, duration: 500, easing: 'ease-out-cubic' })
}

defineExpose({ pulse })

onMounted(render)
watch(() => props.graph, render)
watch(dark, render)
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
