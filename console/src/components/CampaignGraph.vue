<script setup lang="ts">
import cytoscape from 'cytoscape'
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { defang } from '../defang'
import { t } from '../i18n'
import { theme } from '../theme'
import type { Graph } from '../types'

const props = defineProps<{ graph: Graph }>()
const PLAIN_KINDS = new Set(['phone', 'registrar'])
const container = ref<HTMLElement | null>(null)
const showWeak = ref(false)
let cy: cytoscape.Core | null = null

function applyWeak() {
  cy?.edges('[strength = "weak"]').style('display', showWeak.value ? 'element' : 'none')
}

function token(name: string, fallback: string): string {
  try {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
  } catch {
    return fallback
  }
}

function graphStyle(): cytoscape.StylesheetJson {
  const ink = token('--c-ink', '#1f2933')
  const muted = token('--c-muted', '#52606d')
  const hairline = token('--c-hairline', '#9aa5b1')
  const risk = token('--c-risk', '#b42318')
  const surface = token('--c-surface', '#ffffff')
  return [
    { selector: 'node', style: { label: 'data(label)', 'font-size': 10, 'background-color': muted, color: ink, 'text-background-color': surface, 'text-background-opacity': 0.7 } },
    { selector: 'node[kind = "domain"]', style: { 'background-color': risk } },
    { selector: 'edge', style: { width: 2, 'line-color': muted, 'line-style': 'solid' } },
    { selector: 'edge[strength = "weak"]', style: { 'line-style': 'dashed', 'line-color': hairline, display: showWeak.value ? 'element' : 'none' } },
  ] as unknown as cytoscape.StylesheetJson
}

onMounted(() => {
  cy = cytoscape({
    container: container.value,
    elements: [
      ...props.graph.nodes.map(({ data }) => ({
        data: { ...data, id: `n:${data.id}`, label: PLAIN_KINDS.has(data.kind) ? data.label : defang(data.label) },
      })),
      ...props.graph.edges.map(({ data }) => ({
        data: { ...data, id: `e:${data.id}`, source: `n:${data.source}`, target: `n:${data.target}` },
      })),
    ],
    style: graphStyle(),
    layout: { name: 'cose' },
  })
})

watch(theme, () => {
  void nextTick(() => cy?.style(graphStyle()))
})
watch(showWeak, applyWeak)
onBeforeUnmount(() => cy?.destroy())
</script>

<template>
  <label class="check">
    <input v-model="showWeak" type="checkbox" />
    {{ t('showWeak') }}
  </label>
  <div ref="container" class="graph" role="img" :aria-label="t('graph')"></div>
</template>
