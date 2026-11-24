<script setup lang="ts">
import cytoscape from 'cytoscape'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { defang } from '../defang'
import { t } from '../i18n'
import type { Graph } from '../types'

const props = defineProps<{ graph: Graph }>()
const container = ref<HTMLElement | null>(null)
const showWeak = ref(false)
let cy: cytoscape.Core | null = null

function applyWeak() {
  cy?.edges('[strength = "weak"]').style('display', showWeak.value ? 'element' : 'none')
}

onMounted(() => {
  cy = cytoscape({
    container: container.value,
    elements: [
      ...props.graph.nodes.map(({ data }) => ({
        data: { ...data, label: data.kind === 'domain' ? defang(data.label) : data.label },
      })),
      ...props.graph.edges,
    ],
    style: [
      { selector: 'node', style: { label: 'data(label)', 'font-size': 10, 'background-color': '#52606d', color: '#1f2933' } },
      { selector: 'node[kind = "domain"]', style: { 'background-color': '#b42318' } },
      { selector: 'edge', style: { width: 2, 'line-color': '#52606d', 'line-style': 'solid' } },
      { selector: 'edge[strength = "weak"]', style: { 'line-style': 'dashed', 'line-color': '#9aa5b1', display: 'none' } },
    ],
    layout: { name: 'cose' },
  })
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
