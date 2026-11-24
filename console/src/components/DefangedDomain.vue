<script setup lang="ts">
// Attacker-controlled names are shown as defanged text, never as links (docs/admin-dashboard.md decision 6).
// Characters outside ASCII are marked so a Cyrillic "а" inside "uаepass" is visible at a glance.
import { computed } from 'vue'
import { glyphs } from '../defang'

const props = defineProps<{ display: string | null | undefined }>()
const parts = computed(() => glyphs(props.display ?? '—'))
</script>

<template>
  <span class="domain" :title="display ?? ''"><template v-for="(part, i) in parts" :key="i"><mark v-if="part.odd" class="glyph" :title="part.title">{{ part.text }}</mark><template v-else>{{ part.text }}</template></template></span>
</template>
